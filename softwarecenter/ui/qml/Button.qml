import Qt 4.7

Rectangle {
    id: container

    property string text: "ButtonText"
    signal clicked
    
    SystemPalette { id: activePalette }

    Text {
        id: buttontxt
        anchors.centerIn: parent
        color: activePalette.buttonText
        text: container.text
    }
    
    height: buttontxt.height + 10;
    width: buttontxt.width + 10
    border.width: 1
    radius: 4
    smooth: true
    
    MouseArea {
        anchors.fill: parent
        onClicked: {
            container.clicked()
        }
    }
}
