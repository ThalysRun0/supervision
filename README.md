# supervision
Monitoring
## install

git clone \<me\>

```bash
python<version> -m venv supervision
source supervision/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd supervision
# allow power read
sudo chmod +x read_power.sh
ABS_PATH=$(realpath read_power.sh)
grep -qF "$USER ALL=(ALL) NOPASSWD: $ABS_PATH" /etc/sudoers.d/read_power || \
echo "$USER ALL=(ALL) NOPASSWD: $ABS_PATH" | sudo tee /etc/sudoers.d/read_power
sudo visudo -cf /etc/sudoers.d/read_power
# > etc/sudoers.d/read_power: parsed OK

streamlit run app.py
```

### TODO
- **pending** delete warning message about graph for missing label  