#!/usr/bin/env python3
import os
import subprocess
import sys
import getpass
import bcrypt

# Verifica root
if os.geteuid() != 0:
    print("Erro: Este script precisa ser executado como root (sudo).")
    sys.exit(1)

print("=== Setup WG-Easy + Nginx + Firewall (Iptables) + ZERO LOGS ===")

# 1. Perguntas Iniciais
tipo = ""
while tipo not in ['ip', 'dominio']:
    tipo = input("Você vai usar um Domínio ou IP? (digite 'dominio' ou 'ip'): ").strip().lower()

host = input(f"Digite o {tipo}: ").strip()

email = ""
if tipo == 'dominio':
    email = input("Digite seu email (necessário para o certificado Let's Encrypt): ").strip()

dns = input("Qual servidor DNS você quer usar para os clientes VPN? (ex: 1.1.1.1, 8.8.8.8) [Padrão: 1.1.1.1]: ").strip()
if not dns:
    dns = "1.1.1.1"

senha_plana = getpass.getpass("Crie a senha de admin para o painel do WG-Easy: ")
senha_hash = bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
senha_hash_yaml = senha_hash.replace("$", "$$")

print("\nIniciando a instalação e configuração...\n")

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True, executable='/bin/bash')

# 2. Limpeza brutal de lixo antigo e Instalação
print("[1/6] Passando o rodo nas configurações antigas e instalando pacotes...")
run_cmd("dpkg --configure -a || true")
run_cmd("apt-get purge -y docker docker-engine docker.io containerd runc nginx nginx-common nginx-core python3-certbot-nginx || true")
run_cmd("apt-get autoremove -y || true")
run_cmd("rm -rf /etc/nginx || true")

run_cmd("apt-get update")
run_cmd("DEBIAN_FRONTEND=noninteractive apt-get install -y curl wget nginx certbot python3-certbot-nginx iptables-persistent apache2-utils openssl")

print("Instalando o Docker via repositório oficial...")
run_cmd("curl -fsSL https://get.docker.com | sh")

# --- INTEGRAÇÃO: Desativando logs do Docker ---
print("Desativando logs do Docker globalmente...")
os.makedirs("/etc/docker", exist_ok=True)
run_cmd("echo '{\n  \"log-driver\": \"none\"\n}' > /etc/docker/daemon.json")
run_cmd("systemctl restart docker")
# ----------------------------------------------

# 3. Configurando Docker Compose para o wg-easy
print("[2/6] Configurando o wg-easy (Docker)...")
os.makedirs("/opt/wg-easy", exist_ok=True)

docker_compose_yml = f"""
services:
  wg-easy:
    image: ghcr.io/wg-easy/wg-easy
    container_name: wg-easy
    environment:
      - WG_HOST={host}
      - PASSWORD_HASH={senha_hash_yaml}
      - WG_PORT=51820
      - WG_DEFAULT_ADDRESS=10.8.0.x
      - WG_DEFAULT_DNS={dns}
    volumes:
      - /opt/wg-easy:/etc/wireguard
    ports:
      - "51820:51820/udp"
      - "127.0.0.1:51821:51821/tcp"
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
"""
with open("/opt/wg-easy/docker-compose.yml", "w") as f:
    f.write(docker_compose_yml)

run_cmd("cd /opt/wg-easy && docker compose up -d")

# 4. Nginx e SSL
print("[3/6] Configurando Nginx e SSL...")
run_cmd("systemctl enable nginx")

# --- INTEGRAÇÃO: Desativando logs do Nginx ---
run_cmd("sed -i 's/^[ \t]*access_log.*/\taccess_log off;/' /etc/nginx/nginx.conf")
run_cmd("sed -i 's/^[ \t]*error_log.*/\terror_log \/dev\/null emerg;/' /etc/nginx/nginx.conf")
# ---------------------------------------------

nginx_conf = f"""
server {{
    listen 80;
    server_name {host};

    location / {{
        proxy_pass http://127.0.0.1:51821;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }}
}}
"""
with open(f"/etc/nginx/sites-available/wg-easy.conf", "w") as f:
    f.write(nginx_conf)

run_cmd("ln -sf /etc/nginx/sites-available/wg-easy.conf /etc/nginx/sites-enabled/")
run_cmd("rm -f /etc/nginx/sites-enabled/default")
run_cmd("systemctl restart nginx")

if tipo == 'dominio':
    print("Gerando certificado Let's Encrypt...")
    run_cmd(f"certbot --nginx -d {host} --non-interactive --agree-tos -m {email} --redirect")
else:
    print("Gerando certificado Auto-Assinado para IP...")
    run_cmd(f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/nginx-selfsigned.key -out /etc/ssl/certs/nginx-selfsigned.crt -subj '/CN={host}'")
    
    nginx_ssl_conf = f"""
    server {{
        listen 80;
        server_name {host};
        return 301 https://$host$request_uri;
    }}
    server {{
        listen 443 ssl;
        server_name {host};

        ssl_certificate /etc/ssl/certs/nginx-selfsigned.crt;
        ssl_certificate_key /etc/ssl/private/nginx-selfsigned.key;

        location / {{
            proxy_pass http://127.0.0.1:51821;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
        }}
    }}
    """
    with open(f"/etc/nginx/sites-available/wg-easy.conf", "w") as f:
        f.write(nginx_ssl_conf)
    run_cmd("systemctl restart nginx")

# --- INTEGRAÇÃO: Desativando Logs do Sistema e Limpando o Passado ---
print("[4/6] Desativando logs gerais do sistema (journald e rsyslog)...")
run_cmd("sed -i 's/.*Storage=.*/Storage=none/' /etc/systemd/journald.conf")
run_cmd("systemctl restart systemd-journald")
run_cmd("systemctl stop rsyslog || true")
run_cmd("systemctl disable rsyslog || true")

print("Apagando qualquer log residual gerado durante esta instalação...")
run_cmd("find /var/log -type f -exec truncate -s 0 {} \\;")
# --------------------------------------------------------------------

# 5. Firewall Seguro (Iptables)
print("[5/6] Configurando Firewall Iptables...")
run_cmd("iptables -F INPUT")
run_cmd("iptables -P INPUT DROP")
run_cmd("iptables -A INPUT -i lo -j ACCEPT")
run_cmd("iptables -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT")
run_cmd("iptables -A INPUT -p tcp --dport 22 -j ACCEPT")
run_cmd("iptables -A INPUT -p tcp --dport 80 -j ACCEPT")
run_cmd("iptables -A INPUT -p tcp --dport 443 -j ACCEPT")
run_cmd("iptables -A INPUT -p udp --dport 51820 -j ACCEPT")
run_cmd("iptables-save > /etc/iptables/rules.v4")

print("\n[6/6] Concluído! Tudo configurado, rodando e sem registrar logs.")
print(f"Acesse o painel web em: https://{host}")
