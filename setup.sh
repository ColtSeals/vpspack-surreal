
#!/bin/bash
echo ">>> INSTALANDO VPSPACK SURREAL..."

# Instala Python e Flask
apt-get update
apt-get install -y python3 python3-pip sqlite3
pip3 install flask --break-system-packages

# Cria pastas e links
mkdir -p /opt/vpspack
chmod +x menu.py
ln -sf $(pwd)/menu.py /usr/bin/vpspack

# Cria Serviço SystemD (Site rodar no boot)
cat > /etc/systemd/system/vpspack.service <<EOF
[Unit]
Description=VPSPack Web
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vpspack
systemctl restart vpspack

echo ">>> INSTALADO! Digite 'vpspack' ou acesse http://IP:5000"
