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

import QtQuick 1.0

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
        KeyNavigation.down: (listview.x == 0) ? list : null

        Binding {
            target: pkglistmodel
            property: "searchQuery"
            value: navigation.searchQuery
        }

        onSearchQueryChanged: if (searchQuery.length > 0) showListView()
        onSearchActivated: showListView()
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
        anchors.left: catview.right
        anchors.top: navigation.bottom
        anchors.bottom: parent.bottom

        Behavior on x {
            NumberAnimation { duration: 180 }
        }

        AppListView {
            id: list
            model: pkglistmodel
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: statusframe.top

            KeyNavigation.up: navigation
        }

        Rectangle {
            id: statusframe
            height: 20
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            color: activePalette.window

            Rectangle {
                height: 1
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                color: activePalette.mid
            }

            Text {
                anchors.fill: parent
                anchors.margins: 5
                verticalAlignment: Text.AlignVCenter
                text: qsTr("%1 items available").arg(list.count)
            }
        }
    }

    DetailsView {
        id: detailsview
        width: parent.width
        anchors.left: listview.right
        anchors.top: navigation.bottom
        anchors.bottom: parent.bottom

        Behavior on x {
            NumberAnimation { duration: 180 }
        }
    }
}

