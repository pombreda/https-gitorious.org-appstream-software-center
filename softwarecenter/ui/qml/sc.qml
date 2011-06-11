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

FocusScope {
    width: 600
    height: 600
    focus: true

    SystemPalette {
        id: activePalette
        colorGroup: SystemPalette.Active
    }

    NavigationBar {
        id: navigation
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        focus: true
        KeyNavigation.down: (switcher.currentFrame() == listview) ? switcher : null

        Binding {
            target: pkglistmodel
            property: "searchQuery"
            value: navigation.searchQuery
        }

        onHomeClicked: switcher.goToFrame(catview)

        onSearchQueryChanged: if (searchQuery.length > 0) switcher.goToFrame(listview)
        onSearchActivated: switcher.goToFrame(listview)
    }

    FrameSwitcher {
        id: switcher
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: navigation.bottom
        anchors.bottom: parent.bottom
        duration: 180
    }

    Frame {
        id: catview

        CategoriesView {
            anchors.fill: parent
            focus: true
            onCategoryChanged: {
                pkglistmodel.setCategory(catname)
                switcher.goToFrame(listview)
            }
        }
    }

    Frame {
        id: listview

        AppListView {
            id: list
            focus: true
            model: pkglistmodel
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: statusframe.top

            KeyNavigation.up: navigation

            onItemClicked: switcher.focus = true
            onMoreInfoClicked: switcher.goToFrame(detailsview)
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

    Frame {
        id: detailsview

        DetailsView {
            anchors.fill: parent
            focus: true
            onBackClicked: switcher.goToFrame(listview)
        }
    }

    Component.onCompleted: {
        switcher.pushFrame(catview)
        switcher.pushFrame(listview)
        switcher.pushFrame(detailsview)
    }
}

