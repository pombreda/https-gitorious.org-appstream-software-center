import QtQuick 1.0


Rectangle {

    id: root

    width: 600
    height: 400


    Rectangle {

        id: toolbar

        color: "#F2F1F0"
        width: parent.width
        height: 40

        Rectangle {

            color: "white"
            border.color: "#ADADAD"
            radius: 2
            width: 150
            height: 25
            anchors.rightMargin: 4
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter

            TextEdit {

                id: searchEntry

                width: 150
                focus: true
                anchors.margins: 3
                anchors.fill: parent
                verticalAlignment: TextEdit.AlignVCenter

                Keys.onReleased: { 
                    controller.rebuildListFromQuery(searchEntry.text)
                }
            }
        }
    }


    ListView {

        id: pythonList
        anchors.top: toolbar.bottom
        width: parent.width
        height: parent.height
        clip: true

        model: pythonListModel
     
        delegate: Component {

            Rectangle {

                width: pythonList.width
                height: 40
                color: ((index % 2 == 0) ? "#E8E8E8":"#E3E3E3")

                Image {
                    id: icon
                    height: 32
                    width: height
                    anchors.top: parent.top
                    anchors.topMargin: 3
                    anchors.left: parent.left
                    anchors.leftMargin: 3
                    sourceSize.height: height
                    sourceSize.width: width
                    source: model.pkg.icon
                    asynchronous: true
                }

                Text {
                    id: title
                    elide: Text.ElideRight
                    text: model.pkg.name
                    anchors.leftMargin: 10
                    x: icon.x + icon.width + 10
                    verticalAlignment: Text.AlignVCenter
                }


                MouseArea {
                    anchors.fill: parent
                    onClicked: { controller.rowClicked(model.pkg) }
                }
            }
        }

    Image {
        source: "../data/art/dropshadow.png"
        width: parent.width
        anchors.top: parent.top
        opacity: 0.5
    }

    }
}
