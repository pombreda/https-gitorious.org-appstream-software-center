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

    CategoriesView {
        id: catview
        width: parent.width
        height: 100

        onCategoryChanged: {
            pkglistmodel.setCategory(catname)
        }
    }

    Rectangle {
        id: listview
        width: parent.width
        height: parent.height - 100
        color: activePalette.window
        y: 100

        Behavior on x {
            NumberAnimation { duration: 180 }
        }

        Rectangle {
            id: searchframe
            width: parent.width - 20
            height: 30
            anchors.horizontalCenter: parent.horizontalCenter
            y: 10
            color: activePalette.base
            radius: 5

            TextInput {
                id: search
                anchors.fill: parent
                anchors.margins: 5
                focus: true
                KeyNavigation.down: list

                Binding {
                    target: pkglistmodel
                    property: "searchQuery"
                    value: search.text
                }
            }
        }

        AppListView {
            id: list
            model: pkglistmodel
            width: searchframe.width
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: searchframe.bottom
            anchors.topMargin: 10
            anchors.bottom: statusframe.top
            anchors.bottomMargin: 10
            KeyNavigation.up: search
        }

        DetailsView {
            id: details
            width: parent.width
            height: parent.height
            anchors.left: listview.right
        }

        Rectangle {
            id: statusframe
            width: searchframe.width
            height: 30
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            color: activePalette.base
            radius: 5

            Text {
                anchors.fill: parent
                anchors.margins: 5
                text: qsTr("%1 items available").arg(list.count)
            }
        }
    }

}

