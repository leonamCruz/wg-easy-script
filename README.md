# 🚀 Auto-Setup: WG-Easy + Nginx + Iptables

Este script em Python automatiza completamente a instalação e configuração do **WG-Easy** (servidor WireGuard com painel web), protegendo o acesso com **Nginx** (Reverse Proxy + SSL) e trancando as portas desnecessárias com **Iptables**.

Ideal para quem quer subir uma VPN rápida, segura e com interface gráfica em servidores limpos (Debian/Ubuntu). 🛡️

## ✨ Funcionalidades

* 🐳 **Instalação Automática do Docker:** Baixa e configura o Docker diretamente do repositório oficial.
* 🌐 **WG-Easy via Docker Compose:** Sobe o servidor WireGuard e o painel de administração em contêineres.
* 🔒 **Nginx + SSL Automático:**
  * Se usar **Domínio**: Gera e renova certificados válidos via Let's Encrypt (Certbot).
  * Se usar **IP**: Gera certificados auto-assinados automaticamente para garantir criptografia no login.
* 🔑 **Criptografia de Senha Segura:** Hashea sua senha de admin com `bcrypt` antes de salvar no arquivo do Docker.
* 🧱 **Firewall (Iptables) Restrito:** Bloqueia tudo por padrão (Drop) e libera apenas as portas essenciais (SSH, HTTP, HTTPS, WireGuard).

---

## ⚠️ Avisos Importantes

1. **Limpeza Brutal:** O script apaga instalações antigas do Nginx e Docker. **Não rode isso em um servidor que já tenha sites ou serviços em produção!** Ele foi feito para VPS/Servidores novos.
2. **Porta SSH:** O firewall Iptables configurado pelo script libera o SSH na **porta 22 padrão**. Se você usa uma porta SSH customizada, altere a linha `run_cmd("iptables -A INPUT -p tcp --dport 22 -j ACCEPT")` no código antes de rodar, ou você perderá acesso ao servidor!

---
