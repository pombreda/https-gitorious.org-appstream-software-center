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

        property string searchResults: qsTr("Search Results")

        Binding {
            target: pkglistmodel
            property: "searchQuery"
            value: navigation.searchQuery
        }

        onCrumbClicked: {
            if (index == 0) {
                // [Home]
                switcher.goToFrame(catview)
            } else if (index == 1) {
                // Either [Home > categoryName] or [Home > Search Results]
                switcher.goToFrame(listview)
            } else if (index == 2) {
                // Either [Home > categoryName > appName]
                // or [Home > Search Results > appName]
                // or [Home > categoryName > Search Results]
                if (navigation.breadcrumbs.model.get(2).label == searchResults) {
                    switcher.goToFrame(listview)
                } else {
                    switcher.goToFrame(detailsview)
                }
            }
        }

        searchBoxVisible: switcher.currentFrame() != detailsview

        function doSearch() {
            if (searchQuery.length > 0) {
                var bc = navigation.breadcrumbs
                if (bc.count == 1) {
                    // [Home]
                    bc.addCrumb(searchResults)
                } else if (bc.count == 2) {
                    // Either [Home > categoryName] or [Home > Search Results]
                    if (bc.model.get(1).label != searchResults) {
                        bc.addCrumb(searchResults)
                    }
                }
                switcher.goToFrame(listview)
            }
        }
        onSearchQueryChanged: doSearch()
        onSearchActivated: doSearch()
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
                navigation.breadcrumbs.addCrumb(catname)
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

            onMoreInfoClicked: {
                navigation.breadcrumbs.addCrumb(currentItem.appname)
                switcher.goToFrame(detailsview)
            }
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
            id: details
            anchors.fill: parent
            focus: true
            onBackClicked: {
                navigation.breadcrumbs.removeCrumb()
                switcher.goToFrame(listview)
            }
        }
        onShown: details.loadThumbnail()
        onHidden: details.unloadThumbnail()
    }

    Component.onCompleted: {
        switcher.pushFrame(catview)
        switcher.pushFrame(listview)
        switcher.pushFrame(detailsview)
    }
}

