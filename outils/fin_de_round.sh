#!/bin/sh
# Fin de round : tests, autotest, publication, commit — s'arrête au premier échec.
#   sh outils/fin_de_round.sh "notes de version" "message de commit (fichier)"
set -e
cd "$(dirname "$0")/.."
# suite répartie sur plusieurs processus (outils/tests_paralleles.py : 2 à 3 fois plus vite)
QT_QPA_PLATFORM=offscreen python outils/tests_paralleles.py > /tmp/vd_tests.txt 2>&1 || { tail -40 /tmp/vd_tests.txt; echo "TESTS EN ÉCHEC"; exit 1; }
tail -1 /tmp/vd_tests.txt
QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python VectorDrive.py --autotest > /tmp/vd_auto.txt 2>&1 || { tail -20 /tmp/vd_auto.txt; echo "AUTOTEST EN ÉCHEC"; exit 1; }
tail -1 /tmp/vd_auto.txt
PYTHONIOENCODING=utf-8 python outils/publier.py --build --notes "$1" > /tmp/vd_pub.txt 2>&1 || { tail -20 /tmp/vd_pub.txt; echo "PUBLICATION EN ÉCHEC"; exit 1; }
grep -E "setup.exe :|portable.zip :" /tmp/vd_pub.txt
git add -A
git -c user.name=RomDuch -c user.email=romduch@gmail.com commit -q -F "$2"
git log --oneline -1
