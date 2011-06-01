/*
 * Copyright 2011 Canonical Ltd.
 *
 * Authors:
 *  Olivier Tilloy <olivier@tilloy.net>
 *  Michael Vogt <mvo@ubuntu.com>
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

import Qt 4.7

/* Need the experimental desktop components, check them out at
   git://gitorious.org/qt-components/desktop.git */
//import "../qt-components-desktop/components"


Rectangle {
    width: 600
    height: 600

    SystemPalette {
        id: activePalette
        colorGroup: SystemPalette.Active
    }

    function showListView()
    {
        listview.x = listview.x + listview.width
    }

    function showDetailsView()
    {
        listview.x = listview.x - listview.width
        // FIXME: actually we could do this on a property change event
        //        for listview.x, if it changes to "0" trigger load
        reviewslistmodel.getReviews(list.currentItem.pkgname)
    }

    Rectangle {
        id: header
        width: parent.width
        height: searchframe.height + 2*10 // 10px margin 
        color: activePalette.window

        Rectangle {
            id: searchframe
            color: activePalette.base
            width: parent.width - 20
            // FIXME: how can we avoid to hardcode this?
            height: 30 
            y: 10 // offset margins
            x: 10 // offset margins
            radius: 5
            
            TextInput {
                id: search
                anchors.fill: parent
                anchors.margins: 5
                focus: true
                //KeyNavigation.down: list

                Binding {
                    target: pkglistmodel
                    property: "searchQuery"
                    value: search.text
                }
            }
        }
    }

    CategoriesView {
        id: catview
        width: parent.width
        height: 100
        anchors.top: header.bottom

        onCategoryChanged: {
            pkglistmodel.setCategory(catname)
        }
    }

    Rectangle {
        id: listview
        width: parent.width

        color: activePalette.window
        anchors.top: catview.bottom
        anchors.bottom: footer.top

        Behavior on x {
            NumberAnimation { duration: 180 }
        }

        AppListView {
            id: list
            model: pkglistmodel
            width: header.width
            height: listview.height
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 10
            anchors.bottomMargin: 10
            KeyNavigation.up: search
        }

        DetailsView {
            id: details
            width: parent.width
            height: parent.height
            anchors.left: listview.right
        }
    }

    Rectangle {
        id: footer
        width: searchframe.width
        height: 30
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10

        Rectangle {
            id: statusframe
            color: activePalette.base
            radius: 5

            anchors.fill: parent
            Text {
                anchors.fill: parent
                anchors.margins: 5
                text: qsTr("%1 items available").arg(list.count)
            }
        }
    }
}

