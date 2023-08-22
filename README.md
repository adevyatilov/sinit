# Программа sinit
Программа для копирования копирования публичного ssh-ключа на удаленные хосты из файла инвентори Ansible

## Запуск
```bash
# Перемстим файл sinit.py в директорию /usr/local/bin
cp sinit.py /usr/local/bin

# Открываем файл .bashrc
vim ~/.bashrc

# Добавляем alias и сохраняем файл
alias sinit="python3 /usr/local/sinit.py"

# Перечитываем .bashrc
source ~/.bashrc

# Переходим в проект, где находится файл инвентори и запускаем sinit
cd you-ansible-project && sinit
```
