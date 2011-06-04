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

    function showCategoriesView()
    {
        console.log("showCategoryView")
        catview.x = 0
        
        // FIXME: would be nice to do this somewhere else
        pkglistmodel.setCategory("")
    }

    function showListView()
    {
        console.log("showListView")
        catview.x = 0 - listview.width
    }

    function showDetailsView()
    {
        console.log("showDetailsView")
        catview.x =  0 - listview.width - detailsview.width

        // FIXME: actually we could do this on a property change event
        //        for listview.x, if it changes to "0" trigger load
        reviewslistmodel.getReviews(list.currentItem.pkgname)
    }

    NavigationBar {
        id: navigation
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        focus: true
        KeyNavigation.down: list

        Binding {
            target: pkglistmodel
            property: "searchQuery"
            value: navigation.searchQuery
        }

        onSearchQueryChanged: if (searchQuery.length > 0) showListView()
    }

    CategoriesView {
        id: catview
        width: parent.width
        height: parent.height
        anchors.top: navigation.bottom

        Behavior on x {
            NumberAnimation { duration: 180 }
        }
        
        onCategoryChanged: {
            pkglistmodel.setCategory(catname)
            showListView()
        }
    }

    Rectangle {
        id: listview
        width: parent.width

        color: activePalette.window
        anchors.left: catview.right
        anchors.top: navigation.bottom
        anchors.bottom: footer.top

        Behavior on x {
            NumberAnimation { duration: 180 }
        }

        AppListView {
            id: list
            model: pkglistmodel
            anchors.margins: 10
            anchors.fill: parent

            KeyNavigation.up: navigation
        }

        Button {
            id: listbackbtn
            text: qsTr("Back")

            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 15

            onClicked: {
                showCategoriesView();
            }
        }
    }

    DetailsView {
        id: detailsview
        width: parent.width
        anchors.left: listview.right
        anchors.top: navigation.bottom
        anchors.bottom: footer.top

        Behavior on x {
            NumberAnimation { duration: 180 }
        }
    }

    Rectangle {
        id: footer
        width: navigation.width
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

