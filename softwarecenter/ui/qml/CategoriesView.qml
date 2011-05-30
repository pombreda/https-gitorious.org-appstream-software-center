import Qt 4.7

Rectangle {
    clip: true
    id: catview
    width: parent != null ? parent.width : 400
    height: 300

    signal categoryChanged(string catname)

    ScrollBar {
        id: catviewScrollBar
        width: 6; 
        height: catgrid.height - 10
        orientation: Qt.Vertical
        
        anchors.right: parent.right
        position: catgrid.visibleArea.yPosition
        pageSize: catgrid.visibleArea.heightRatio
    }

    GridView {
        id: catgrid
        width: parent.width - 10
        height: parent.height - 10
        focus: true

        // FIXME: how can we avoid to hardcode this?
        cellWidth: 200
        cellHeight: 100

        model: categoriesmodel
        delegate: categoriesDelegate
        
        highlight: Rectangle { 
            color: "lightsteelblue"; radius: 5
        }
        
        Component {
            id: categoriesDelegate

            Item {
                property string catname: _name
                property string caticon: _iconname

                width: catgrid.cellWidth
                height: catgrid.cellHeight

                Image {
                    id: caticonimg
                    source: caticon
                    anchors.horizontalCenter: parent.horizontalCenter
                }
                
                Text { 
                    id: catnametxt
                    text: catname
                    anchors.top: caticonimg.bottom
                    anchors.horizontalCenter: parent.horizontalCenter 
                }

                MouseArea {
                    anchors.fill: parent
                    
                    onClicked: {
                        // mvo: this works fine, but where is "index" actualy
                        //      set/definied?
                        catgrid.currentIndex = index    
                        catview.categoryChanged(catname)
                    }
                }
            }
        }
    }
}