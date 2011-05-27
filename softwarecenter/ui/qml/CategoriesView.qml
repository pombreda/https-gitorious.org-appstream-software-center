import Qt 4.7

Rectangle {
    clip: true
    id: catview
    width: parent != null ? parent.width : 300
    height: 300

    ScrollBar {
        id: catviewScrollBar
        width: 6; 
        height: catlist.height - 10
        orientation: Qt.Vertical
        
        anchors.right: parent.right
        position: catlist.visibleArea.yPosition
        pageSize: catlist.visibleArea.heightRatio
    }

    GridView {
        id: catlist
        width: parent.width - 10
        height: parent.height - 10
        model: categoriesmodel
        focus: true
        
        highlight: Rectangle { 
            color: "lightsteelblue"; radius: 5
        }
        
        delegate: Column {
            property string catname: _name
            property string caticon: _iconname
            
            Image {
                id: caticonimg
                source: caticon
                anchors.horizontalCenter: parent.horizontalCenter
            }
            
            Text { 
                id: catnametxt
                text: catname
                anchors.horizontalCenter: parent.horizontalCenter 
            }
            
            MouseArea {
                // FIXME: this generates a rather ugly warning,
                //        but it appears to work?!?
                anchors.fill: caticonimg
                
                onClicked: {
                    // mvo: this works fine, but where is "index" actualy
                    //      set/definied?
                    catlist.currentIndex = index
                }
            }
        }
    }
}