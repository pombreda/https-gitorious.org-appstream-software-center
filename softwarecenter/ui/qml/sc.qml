import Qt 4.7

/* Need the experimental desktop components, check them out at
   git://gitorious.org/qt-components/desktop.git */
//import "../qt-components-desktop/components"


Rectangle {
    width: 600
    height: 600

    SystemPalette { id: activePalette }

    Rectangle {
        id: listview
        width: parent.width
        height: parent.height
        color: "lightsteelblue"

        Behavior on x {
            NumberAnimation { duration: 180 }
        }

        Rectangle {
            id: searchframe
            width: parent.width - 20
            height: 30
            anchors.horizontalCenter: parent.horizontalCenter
            y: 10
            color: "white"
            radius: 5
            
            TextInput {
                id: search
                anchors.fill: parent
                anchors.margins: 5
                focus: true
                KeyNavigation.down: list

                Keys.onReleased: {
                    pkglistmodel.searchQuery = search.text
                }               
            }
        }

        Rectangle {
            id: listframe
            width: searchframe.width
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: searchframe.bottom
            anchors.topMargin: 10
            anchors.bottom: statusframe.top
            anchors.bottomMargin: 10
            color: "white"
            radius: 5
            clip: true

            ListView {
                id: list
                width: parent.width - 10
                height: parent.height - 10
                anchors.centerIn: parent
                spacing: 5
                KeyNavigation.up: search

                model: pkglistmodel

                delegate: Rectangle {
                    property string appname: _appname
                    property string pkgname: _pkgname
                    property string icon: _icon
                    property string summary: _summary
                    property bool installed: _installed
                    property string description: _description
                    property int installremoveprogress: _installremoveprogress
                
                    width: parent.width
                    height: ListView.isCurrentItem ? 75 : 40
                    Behavior on height {
                        NumberAnimation { duration: 40 }
                    }

                    radius: 5
                    color: {
                        if (!ListView.isCurrentItem) return "white"
                        if (list.activeFocus) return "#F07746"
                        else return "#E1DFDD"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            list.focus = true
                            list.currentIndex = index
                        }
                    }

                    Image {
                        id: iconimg
                        height: 24
                        width: height
                        anchors.top: parent.top
                        anchors.topMargin: 3
                        anchors.left: parent.left
                        anchors.leftMargin: 3
                        sourceSize.height: height
                        sourceSize.width: width
                        source: icon
                        asynchronous: true

                        Image {
                            id: installedemblem
                            height: 16
                            width: height
                            sourceSize.height: height
                            sourceSize.width: width
                            source: "file:///usr/share/software-center/icons/software-center-installed.png"
                            anchors.horizontalCenter: parent.right
                            anchors.verticalCenter: parent.bottom
                            asynchronous: true
                            visible: installed
                        }
                    }
                    Text {
                        id: appnametxt
                        height: 20
                        anchors.top: parent.top
                        anchors.topMargin: 3
                        width: parent.width - iconimg.witdh - 15
                        x: iconimg.x + iconimg.width + 10
                        text: appname
                    }
                    Text {
                        id: summarytxt
                        height: 20
                        anchors.top: appnametxt.bottom
                        width: appnametxt.width
                        x: appnametxt.x
                        font.pointSize:  appnametxt.font.pointSize * 0.8
                        text: summary
                    }

                    Rectangle {
                        id: installremoveprogressbar
                        x: parent.width - 100 -10
                        anchors.top: appnametxt.top
                        anchors.margins: 10
                        height: appnametxt.height
                        color: "steelblue"
                        visible:  parent.ListView.isCurrentItem
                        width: installremoveprogress 
                    }

                    Button {
                        id: moreinfobtn
                        text: "More Info"

                        anchors.top: summarytxt.bottom
                        x: summarytxt.x
                        visible: parent.ListView.isCurrentItem

                        onClicked: {
                            listview.x = listview.x - listview.width
                        }
                    }
                    Button {
                        text: installed ? "Remove" : "Install"

                        anchors.top: summarytxt.bottom
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        visible: parent.ListView.isCurrentItem

                        onClicked: {
                            if (installed) 
                                pkglistmodel.removePackage(pkgname)
                            else
                                pkglistmodel.installPackage(pkgname)
                        }
                    }

                }
            }
        }

        Rectangle {
            id: statusframe
            width: searchframe.width
            height: 30
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            color: "white"
            radius: 5

            Text {
                anchors.fill: parent
                anchors.margins: 5
                text: list.count + " items available"
            }
        }
    }

    Rectangle {
        id: detailsview
        width: parent.width
        height: parent.height
        anchors.left: listview.right
        color: "lightsteelblue"

        Rectangle {
            id: detailsframe
            anchors.fill: parent
            anchors.margins: 10
            color: "white"
            radius: 5

            Rectangle {
                anchors.left: parent. left
                anchors.right: parent.right
                height: 150
                radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#B2CFE7" }
                    GradientStop { position: 1.0; color: "white" }
                }
                Image {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    source: "file:///usr/share/software-center/images/clouds.png"
                    asynchronous: true
                }
            }

            Image {
                id: largeiconimg
                height: 64
                width: height
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.margins: 15
                sourceSize.height: height
                sourceSize.width: width
                source: list.currentItem.icon
                asynchronous: true
            }

            Text {
                id: titletxt
                anchors.top: parent.top
                anchors.left: largeiconimg.right
                anchors.right: parent.right
                anchors.margins: 15
                height: 25
                font.pointSize: 20
                font.bold: true
                text: list.currentItem.appname
            }

            Text {
                id: headertxt
                anchors.top: titletxt.bottom
                anchors.topMargin: 5
                anchors.left: largeiconimg.right
                anchors.right: parent.right
                anchors.margins: 15
                height: 10
                font.pointSize: 9
                text: list.currentItem.summary
            }

            Text {
                id: desctxt
                anchors.top: headertxt.bottom
                anchors.topMargin: 50
                anchors.left: parent.left
                anchors.right: screenshotthumb.left
                anchors.margins: 15
                height: 200
                text: list.currentItem.description
                wrapMode: Text.Wrap
            }

            Image {
                id: screenshotthumb
                anchors.top: headertxt.bottom
                anchors.topMargin: 50
                anchors.right: parent.right
                anchors.margins: 15
                height: 100
                width: 150
                sourceSize.height: height
                sourceSize.width: width

                // FIXME: this is currently loaded everytime someone
                //        clicks on a icon in the listview! 
                //        - load *only* when on the appropriate page
                source: "http://screenshots.ubuntu.com/thumbnail/" + list.currentItem.pkgname
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        screenshotview.loadScreenshot("http://screenshots.ubuntu.com/screenshot/" + list.currentItem.pkgname)
                    }
                }
            }
           Button {
               id: backbtn
               anchors.left: parent.left
               anchors.bottom: parent.bottom
               anchors.margins: 15
               text: "Back"
               
               onClicked: {
                   listview.x = listview.x + listview.width
                   search.focus = true
               }
           }
        }
    }

    Rectangle {
        id: screenshotview
        width: parent.width
        height: parent.height
        anchors.left: detailsview.left
        opacity: 0.0
        color: "lightsteelblue"

        Behavior on opacity {
            NumberAnimation {
                duration: 300
            }
        }

        function loadScreenshot(url) {
            screenshotfullimg.source = url
            fadeIn()
        }

        function fadeIn() {
            opacity = 1.0
        }

        function fadeOut() {
            opacity = 0.0
        }

        Rectangle {
            id: screenshotframe
            anchors.fill: parent
            anchors.margins: 10
            color: "white"
            radius: 5

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                height: 150
                radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#B2CFE7" }
                    GradientStop { position: 1.0; color: "white" }
                }
                Image {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    source: "file:///usr/share/software-center/images/clouds.png"
                    asynchronous: true
                }
            }
            
            Text {
                id: screenshottitle
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 15
                height: 25
                font.pointSize: 14
                font.bold: true
                text: "Screenshot for " + list.currentItem.appname
            }

            Image {
                id: screenshotfullimg
                anchors.top: screenshottitle.bottom
                anchors.right: parent.right
                anchors.margins: 20
                width: parent.width - 50
                sourceSize.width: width

                asynchronous: true

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        screenshotview.fadeOut()
                    }
                }
            }
            Button {
                id: screenshotbackbtn
                text: "Done"

                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.margins: 15

                onClicked: {
                    screenshotview.fadeOut()
                }
            }
        }
    }
}

