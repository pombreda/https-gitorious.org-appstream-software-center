/*
 * Copyright 2011 Canonical Ltd.
 *
 * Authors:
 *  Olivier Tilloy <olivier@tilloy.net>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import QtQuick 1.0

FocusScope {
    id: applistview

    property alias count: list.count
    property alias currentItem: list.currentItem
    property alias model: list.model

    clip: true

    Rectangle {
        color: activePalette.base
        anchors.fill: parent
    }

    ScrollBar {
        id: scrollbar
        width: 6
        height: parent.height
        orientation: Qt.Vertical

        anchors.right: parent.right
        position: list.visibleArea.yPosition
        pageSize: list.visibleArea.heightRatio
        visible: list.count > 0
    }

    ListView {
        id: list
        height: parent.height
        anchors.left: parent.left
        anchors.right: scrollbar.left
        spacing: 5
        focus: true

        SystemPalette {
            id: activePalette
            colorGroup: SystemPalette.Active
        }

        SystemPalette {
            id: inactivePalette
            colorGroup: SystemPalette.Inactive
        }

        delegate: Rectangle {
            property string appname: _appname
            property string pkgname: _pkgname
            property string icon: _icon
            property string summary: _summary
            property bool installed: _installed
            property string description: _description
            property double ratingsaverage: _ratings_average
            property int ratingstotal: _ratings_total
            property int installremoveprogress: _installremoveprogress
        
            width: parent.width
            height: ListView.isCurrentItem ? 75 : 40
            Behavior on height {
                NumberAnimation { duration: 40 }
            }

            color: {
                if (!ListView.isCurrentItem) return activePalette.base
                if (list.activeFocus) return activePalette.highlight
                else return inactivePalette.highlight
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    applistview.focus = true
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

            // ratings row
            Row {
                id: ratingsaverageimg
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 5
                visible: (ratingstotal > 0)
                Repeater {
                    model: Math.floor(ratingsaverage)
                    Image {
                        source: "../../../data/images/star-yellow.png"
                    }
                }
                Image {
                    source: "../../../data/images/star-half.png"
                    visible: { Math.floor(ratingsaverage) != 
                               Math.ceil(ratingsaverage) }
                }
                Repeater {
                    model: 5-Math.ceil(ratingsaverage)
                    Image {
                        source: "../../../data/images/star-dark.png"
                    }
                }
            }

            // ratings total text
            Text {
                id: ratingstotaltxt
                text: String(ratingstotal) + " Ratings"
                anchors.top: ratingsaverageimg.bottom
                anchors.right: ratingsaverageimg.right
                visible: (ratingstotal > 0)
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
                text: qsTr("More Info")

                anchors.top: summarytxt.bottom
                x: summarytxt.x
                visible: parent.ListView.isCurrentItem

                onClicked: {
                    showDetailsView()
                }
            }

            Button {
                text: installed ? qsTr("Remove") : qsTr("Install")

                anchors.top: summarytxt.bottom
                anchors.right: parent.right
                anchors.rightMargin: 10
                visible: parent.ListView.isCurrentItem

                onClicked: {
                    if (installed) 
                        list.model.removePackage(pkgname)
                    else
                        list.model.installPackage(pkgname)
                }
            }
        }
    }
}

