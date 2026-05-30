#!/bin/bash
echo "Memulai proses pembaruan sistem..." > update.log
date >> update.log

cd /home/gemini/web-skripsi
echo "Pulling dari Git (branch production)..." >> update.log
git pull origin production >> update.log 2>&1

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "Membangun Docker Image untuk Web Backend..." >> update.log
sudo docker build -t smartdoor-web:latest -f Dockerfile.app . >> update.log 2>&1

echo "Membangun Docker Image untuk Access Control..." >> update.log
sudo docker build -t smartdoor-access:latest -f Dockerfile.server . >> update.log 2>&1

echo "Memberi tag pada Face Registration..." >> update.log
sudo docker tag smartdoor-access:latest smartdoor-reg:latest >> update.log 2>&1

echo "Mengimpor Image ..." >> update.log
sudo docker save smartdoor-web:latest | sudo k3s ctr images import - >> update.log 2>&1
sudo docker save smartdoor-access:latest | sudo k3s ctr images import - >> update.log 2>&1
sudo docker save smartdoor-reg:latest | sudo k3s ctr images import - >> update.log 2>&1

echo "Melakukan Restart..." >> update.log
sudo kubectl rollout restart deployment -n smart-door-skripsi >> update.log 2>&1

echo "SELESAI! Sistem berhasil diperbarui." >> update.log
date >> update.log
