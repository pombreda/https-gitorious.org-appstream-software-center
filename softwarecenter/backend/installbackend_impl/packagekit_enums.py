# Copyright (C) 2007-2008 Richard Hughes <richard@hughsie.com>
#               2011 Giovanni Campagna <scampa.giovanni@gmail.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

# stolen from gnome-packagekit, which is GPL2+

from gi.repository import PackageKitGlib as packagekit
from gettext import gettext as _

def status_enum_to_localised_text (status):
    if status == packagekit.StatusEnum.UNKNOWN:
        # TRANSLATORS: This is when the transaction status is not known 
        return _("Unknown state")
    elif status == packagekit.StatusEnum.SETUP:
        # TRANSLATORS: transaction state, the daemon is in the process of starting 
        return _("Starting")
    elif status == packagekit.StatusEnum.WAIT:
        # TRANSLATORS: transaction state, the transaction is waiting for another to complete 
        return _("Waiting in queue")
    elif status == packagekit.StatusEnum.RUNNING:
        # TRANSLATORS: transaction state, just started 
        return _("Running")
    elif status == packagekit.StatusEnum.QUERY:
        # TRANSLATORS: transaction state, is querying data 
        return _("Querying")
    elif status == packagekit.StatusEnum.INFO:
        # TRANSLATORS: transaction state, getting data from a server 
        return _("Getting information")
    elif status == packagekit.StatusEnum.REMOVE:
        # TRANSLATORS: transaction state, removing packages 
        return _("Removing packages")
    elif status == packagekit.StatusEnum.DOWNLOAD:
        # TRANSLATORS: transaction state, downloading package files 
        return _("Downloading packages")
    elif status == packagekit.StatusEnum.INSTALL:
        # TRANSLATORS: transaction state, installing packages 
        return _("Installing packages")
    elif status == packagekit.StatusEnum.REFRESH_CACHE:
        # TRANSLATORS: transaction state, refreshing internal lists 
        return _("Refreshing software list")
    elif status == packagekit.StatusEnum.UPDATE:
        # TRANSLATORS: transaction state, installing updates 
        return _("Installing updates")
    elif status == packagekit.StatusEnum.CLEANUP:
        # TRANSLATORS: transaction state, removing old packages, and cleaning config files 
        return _("Cleaning up packages")
    elif status == packagekit.StatusEnum.OBSOLETE:
        # TRANSLATORS: transaction state, obsoleting old packages 
        return _("Obsoleting packages")
    elif status == packagekit.StatusEnum.DEP_RESOLVE:
        # TRANSLATORS: transaction state, checking the transaction before we do it 
        return _("Resolving dependencies")
    elif status == packagekit.StatusEnum.SIG_CHECK:
        # TRANSLATORS: transaction state, checking if we have all the security keys for the operation 
        return _("Checking signatures")
    elif status == packagekit.StatusEnum.ROLLBACK:
        # TRANSLATORS: transaction state, when we return to a previous system state 
        return _("Rolling back")
    elif status == packagekit.StatusEnum.TEST_COMMIT:
        # TRANSLATORS: transaction state, when we're doing a test transaction 
        return _("Testing changes")
    elif status == packagekit.StatusEnum.COMMIT:
        # TRANSLATORS: transaction state, when we're writing to the system package database 
        return _("Committing changes")
    elif status == packagekit.StatusEnum.REQUEST:
        # TRANSLATORS: transaction state, requesting data from a server 
        return _("Requesting data")
    elif status == packagekit.StatusEnum.FINISHED:
        # TRANSLATORS: transaction state, all done! 
        return _("Finished")
    elif status == packagekit.StatusEnum.CANCEL:
        # TRANSLATORS: transaction state, in the process of cancelling 
        return _("Cancelling")
    elif status == packagekit.StatusEnum.DOWNLOAD_REPOSITORY:
        # TRANSLATORS: transaction state, downloading metadata 
        return _("Downloading repository information")
    elif status == packagekit.StatusEnum.DOWNLOAD_PACKAGELIST:
        # TRANSLATORS: transaction state, downloading metadata 
        return _("Downloading list of packages")
    elif status == packagekit.StatusEnum.DOWNLOAD_FILELIST:
        # TRANSLATORS: transaction state, downloading metadata 
        return _("Downloading file lists")
    elif status == packagekit.StatusEnum.DOWNLOAD_CHANGELOG:
        # TRANSLATORS: transaction state, downloading metadata 
        return _("Downloading lists of changes")
    elif status == packagekit.StatusEnum.DOWNLOAD_GROUP:
        # TRANSLATORS: transaction state, downloading metadata 
        return _("Downloading groups")
    elif status == packagekit.StatusEnum.DOWNLOAD_UPDATEINFO:
        # TRANSLATORS: transaction state, downloading metadata 
        return _("Downloading update information")
    elif status == packagekit.StatusEnum.REPACKAGING:
        # TRANSLATORS: transaction state, repackaging delta files 
        return _("Repackaging files")
    elif status == packagekit.StatusEnum.LOADING_CACHE:
        # TRANSLATORS: transaction state, loading databases 
        return _("Loading cache")
    elif status == packagekit.StatusEnum.SCAN_APPLICATIONS:
        # TRANSLATORS: transaction state, scanning for running processes 
        return _("Scanning installed applications")
    elif status == packagekit.StatusEnum.GENERATE_PACKAGE_LIST:
        # TRANSLATORS: transaction state, generating a list of packages installed on the system 
        return _("Generating package lists")
    elif status == packagekit.StatusEnum.WAITING_FOR_LOCK:
        # TRANSLATORS: transaction state, when we're waiting for the native tools to exit 
        return _("Waiting for package manager lock")
    elif status == packagekit.StatusEnum.WAITING_FOR_AUTH:
        # TRANSLATORS: waiting for user to type in a password 
        return _("Waiting for authentication")
    elif status == packagekit.StatusEnum.SCAN_PROCESS_LIST:
        # TRANSLATORS: we are updating the list of processes 
        return _("Updating the list of running applications")
    elif status == packagekit.StatusEnum.CHECK_EXECUTABLE_FILES:
        # TRANSLATORS: we are checking executable files in use 
        return _("Checking for applications currently in use")
    elif status == packagekit.StatusEnum.CHECK_LIBRARIES:
        # TRANSLATORS: we are checking for libraries in use 
        return _("Checking for libraries currently in use")
    elif status == packagekit.StatusEnum.COPY_FILES:
        # TRANSLATORS: we are copying package files to prepare to install 
        return _("Copying files")
    else:
        return "status unrecognised: %s" % packagekit.status_enum_to_string (status)

def role_enum_to_localised_present (role):
    if role == packagekit.RoleEnum.GET_DEPENDS:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting dependencies")
    elif role == packagekit.RoleEnum.GET_UPDATE_DETAIL:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting update detail")
    elif role == packagekit.RoleEnum.GET_DETAILS:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting details")
    elif role == packagekit.RoleEnum.GET_REQUIRES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting requires")
    elif role == packagekit.RoleEnum.GET_UPDATES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting updates")
    elif role == packagekit.RoleEnum.SEARCH_DETAILS:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Searching details")
    elif role == packagekit.RoleEnum.SEARCH_FILE:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Searching for file")
    elif role == packagekit.RoleEnum.SEARCH_GROUP:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Searching groups")
    elif role == packagekit.RoleEnum.SEARCH_NAME:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Searching for package name")
    elif role == packagekit.RoleEnum.REMOVE_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Removing")
    elif role == packagekit.RoleEnum.INSTALL_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Installing")
    elif role == packagekit.RoleEnum.INSTALL_FILES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Installing file")
    elif role == packagekit.RoleEnum.REFRESH_CACHE:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Refreshing package cache")
    elif role == packagekit.RoleEnum.UPDATE_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Updating packages")
    elif role == packagekit.RoleEnum.UPDATE_SYSTEM:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Updating system")
    elif role == packagekit.RoleEnum.CANCEL:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Canceling")
    elif role == packagekit.RoleEnum.ROLLBACK:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Rolling back")
    elif role == packagekit.RoleEnum.GET_REPO_LIST:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting list of repositories")
    elif role == packagekit.RoleEnum.REPO_ENABLE:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Enabling repository")
    elif role == packagekit.RoleEnum.REPO_SET_DATA:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Setting repository data")
    elif role == packagekit.RoleEnum.RESOLVE:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Resolving")
    elif role == packagekit.RoleEnum.GET_FILES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting file list")
    elif role == packagekit.RoleEnum.WHAT_PROVIDES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting what provides")
    elif role == packagekit.RoleEnum.INSTALL_SIGNATURE:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Installing signature")
    elif role == packagekit.RoleEnum.GET_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting package lists")
    elif role == packagekit.RoleEnum.ACCEPT_EULA:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Accepting EULA")
    elif role == packagekit.RoleEnum.DOWNLOAD_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Downloading packages")
    elif role == packagekit.RoleEnum.GET_DISTRO_UPGRADES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting distribution upgrade information")
    elif role == packagekit.RoleEnum.GET_CATEGORIES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting categories")
    elif role == packagekit.RoleEnum.GET_OLD_TRANSACTIONS:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Getting old transactions")
    elif role == packagekit.RoleEnum.SIMULATE_INSTALL_FILES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Simulating the install of files")
    elif role == packagekit.RoleEnum.SIMULATE_INSTALL_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Simulating the install")
    elif role == packagekit.RoleEnum.SIMULATE_REMOVE_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense 
        return _("Simulating the remove")
    elif role == packagekit.RoleEnum.SIMULATE_UPDATE_PACKAGES:
        # TRANSLATORS: The role of the transaction, in present tense
        return _("Simulating the update")
    elif role == packagekit.RoleEnum.UPGRADE_SYSTEM:
        # TRANSLATORS: The role of the transaction, in present tense
        return _("Upgrading system")
    else:
        return "role unrecognised: %s" % packagekit.role_enum_to_string (role)
