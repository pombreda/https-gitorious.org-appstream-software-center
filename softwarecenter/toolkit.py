import sys

class UIToolkits:
    GTK2 = 0
    GTK3 = 1
    QML = 2
    FALLBACK = GTK2


if 'software-center-gtk3' in sys.argv[0]:
    CURRENT_TOOLKIT = UIToolkits.GTK3
elif 'software-center-gtk' in sys.argv[0]:
    CURRENT_TOOLKIT = UIToolkits.GTK2
elif 'software-center-qml' in sys.argv[0]:
    CURRENT_TOOLKIT = UIToolkits.QML
else:
    CURRENT_TOOLKIT = UIToolkits.FALLBACK
