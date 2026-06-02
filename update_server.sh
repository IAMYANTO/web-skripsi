#!/bin/bash
echo "=== DEPLOY PIPELINE START ===" > update.log
date >> update.log

cd /home/gemini/web-skripsi
echo "[1/5] Pulling dari Git (branch production)..." >> update.log
git fetch origin production >> update.log 2>&1
git reset --hard origin/production >> update.log 2>&1
git clean -fd >> update.log 2>&1

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "[2/5] Membangun Docker Image: smartdoor-web..." >> update.log
sudo docker build -t smartdoor-web:latest -f Dockerfile.app . >> update.log 2>&1

echo "[3/5] Membangun Docker Image: smartdoor-access..." >> update.log
sudo docker build -t smartdoor-access:latest -f Dockerfile.server . >> update.log 2>&1

echo "[4/5] Mengimpor Image ke K3s containerd..." >> update.log
sudo docker save smartdoor-web:latest | sudo k3s ctr images import - >> update.log 2>&1
sudo docker save smartdoor-access:latest | sudo k3s ctr images import - >> update.log 2>&1

echo "[5/5] Restart Pods di Kubernetes..." >> update.log
sudo kubectl rollout restart deployment -n smart-door-skripsi >> update.log 2>&1

echo "=== DEPLOY PIPELINE SELESAI ===" >> update.log
date >> update.log
