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


Row {
    property double ratings_average

    Repeater {
        model: Math.floor(ratings_average)
        Image {
            source: "../../../data/images/star-yellow.png"
        }
    }
    Image {
        source: "../../../data/images/star-half.png"
        visible: Math.floor(ratings_average) != Math.ceil(ratings_average)
    }
    Repeater {
        model: 5 - Math.ceil(ratings_average)
        Image {
            source: "../../../data/images/star-dark.png"
        }
    }
}
