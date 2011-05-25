import Qt 4.7

Rectangle {
    property string text: "ButtonText"
    signal clicked
    
    SystemPalette { id: activePalette }

    Text {
        id: buttontxt
        anchors.centerIn: parent
        text: parent.text
        color: activePalette.buttonText
    }

    width: buttontxt.width + 10
    height: buttontxt.height + 10

    radius: 4
    border.width: 1
    border.color: activePalette.shadow
    color: mousearea.containsMouse && !mousearea.pressed ? activePalette.light : activePalette.button
    
    MouseArea {
        id: mousearea
        anchors.fill: parent
        hoverEnabled: true
        onClicked: parent.clicked()
    }
}
