# -*- coding: utf-8 -*-
###
### SmartModules > Context Updater
###
from lib.db.Credential import Credential
from lib.db.Option import Option
from lib.db.Product import Product
from lib.db.Vuln import Vuln
from lib.core.Config import *
from lib.output.Logger import logger
from lib.utils.OSUtils import OSUtils
from lib.utils.VersionUtils import VersionUtils


class ContextUpdater:

    def __init__(self, service, command_output_id=None):
        """
        ContextUpdater is used to update information related to a given service.
        It is used by smart modules during attack initialization and when analyzing
        command outputs.

        :param Service service: Service model
        :param int command_output_id: Id of the CommandOutput object storing the 
            command output from which the analysis is performed. Used when called from
            SmartPostcheck class, None otherwise.
        """
        self.service = service
        self.command_output_id = command_output_id
        self.specific_options = list()
        self.usernames = list()
        self.credentials = list()
        self.products = list()
        self.vulns = list()
        self.os = ''


    #------------------------------------------------------------------------------------
    # Add detected element

    def add_option(self, name, value):
        """
        Add new Specific Option to the context.

        :param str name: Option name
        :param str value: Option value
        """
        self.specific_options.append(Option(name=name, value=value))


    def add_username(self, username, auth_type=None):
        """
        Add new Username (Credential with no password known) to the context.

        :param str username: Username
        :param str auth_type: Authentication type for HTTP (None otherwise)
        """
        # Do not add two times the same username
        for u in self.usernames:
            if u.type == auth_type and u.username == username and u.password == None:
                return
                
        if auth_type:
            auth_type = auth_type.lower()

        self.usernames.append(
            Credential(
                type=auth_type, 
                username=username, 
                password=None,
                command_output_id=self.command_output_id))


    def add_credentials(self, username, password, auth_type=None):
        """
        Add new Credential (username and password known) to the context.

        :param str username: Username
        :param str password: Password ('' for empty password)
        :param str auth_type: Authentication type for HTTP (None otherwise)        
        """
        # Do not add too times the same credentials
        for c in self.credentials:
            if c.type == auth_type and c.username == username and c.password == password:
                return

        if auth_type:
            auth_type = auth_type.lower()
            
        self.credentials.append(
            Credential(
                type=auth_type, 
                username=username, 
                password=password,
                command_output_id=self.command_output_id))


    def add_product(self, type_, name, version):
        """
        Add new Product to the context.

        :param str type_: Product type
        :param str name: Product name
        :param str version: Product version('' if unknown)
        """
        self.products.append(
            Product(type=type_, name=name, version=version))


    def add_vuln(self, 
                 name, 
                 location,
                 reference,
                 score,
                 link,
                 exploit_available,
                 exploited):
        """
        Add new Vuln to the context.

        :param str name: Vulnerability name (mandatory)
        :param str location: Location of vulnerability (optional)
        :param str reference: Reference of vulnerability (optional)
        :param float score: CVSS Score (optional)
        :param str link: Link to vulnerability information (optional)
        :param bool exploit_available: Indicator of exploit availability (optional)
        :param bool exploited: Indicator of exploitation of the vulnerability (optional)
        """
        self.vulns.append(Vuln(
            name=name,
            location=location,
            reference=reference,
            score=score,
            link=link,
            exploit_available=exploit_available,
            exploited=exploited,
            command_output_id=self.command_output_id))


    def add_os(self, os):
        self.os = os


    #------------------------------------------------------------------------------------
    # Update database

    def update(self):
        """Update service's context and make change persistent in database"""
        self.__update_specific_options()
        self.__update_usernames()
        self.__update_credentials()
        self.__update_products()
        self.__update_vulns()
        self.__update_os()


    #------------------------------------------------------------------------------------

    def __update_specific_options(self):
        """Update service's specific options (table "options")"""
        for option in self.specific_options:
            match_option = self.service.get_option(option.name)
            if match_option:
                if match_option.value == option.value:
                    logger.smartinfo('Detected option (already known): {name} = ' \
                        '{old}'.format(name=option.name, old=match_option.value))
                else:
                    logger.smartsuccess('Change option: {name} = {old} -> {new}'.format(
                        name=option.name, old=match_option.value, new=option.value))
                    match_option.value = option.value
            else:
                logger.smartsuccess('New detected option: {name} = {new}'.format(
                    name=option.name, new=option.value))
                self.service.options.append(option)


    #------------------------------------------------------------------------------------

    def __update_usernames(self):
        """
        Update service's usernames (in table "credentials").
        This is called when only valid username has been found (but not the 
        associated password).
        """
        for username in self.usernames:
            username_str = '{username} {auth_type}'.format(
                username=username.username or '<empty>',
                auth_type='(type='+username.type+')' if username.type else '')

            match_cred = self.service.get_credential(username.username, username.type)
            if match_cred:
                if match_cred.password is None:
                    logger.smartinfo('Detected username (already known): {}'.format(
                        username_str))
                else:
                    logger.smartinfo('Detected username (password already ' \
                        'known): {}'.format(username_str))
            else:
                logger.smartsuccess('New detected username: {}'.format(username_str))
                self.service.credentials.append(username)


    #------------------------------------------------------------------------------------

    def __update_credentials(self):
        """Update service's credentials (username+password) (in table "credentials")"""
        for credential in self.credentials:
            credential_str = '{username}/{password} {auth_type}'.format(
                username=credential.username or '<empty>',
                password=credential.password or '<empty>',
                auth_type='(type='+credential.type+')' if credential.type else '')

            match_cred = self.service.get_credential(
                credential.username, credential.type)
            if match_cred:
                if match_cred.password is None:
                    logger.smartsuccess('Credentials found (username already ' \
                        'known): {}'.format(credential_str))
                    match_cred.password = credential.password
                elif match_cred.password != credential.password:
                    logger.smartsuccess('Credentials found (new password): {}'.format(
                        credential_str))
                    match_cred.password = credential.password
                else:
                    logger.smartinfo('Credentials detected (already in db): {}'.format(
                        credential_str))
            else:
                logger.smartsuccess('New Credentials found: {}'.format(credential_str))
                self.service.credentials.append(credential)


    #------------------------------------------------------------------------------------

    def __update_products(self):
        """Update service's products (in table "products")"""
        for product in self.products:
            product_str = '{type}={name}'.format(
                type=product.type,
                name=product.name)

            match_product = self.service.get_product(product.type, product.name)

            # Same type + name already present in database
            if match_product:
                # # Same product name detected
                # if match_product.name == product.name:

                # Version detected
                if product.version:

                    # Version freshly detected
                    if match_product.version == '':
                        logger.smartsuccess('Version detected for product ' \
                            '{product}: {version}'.format(
                                product=product_str,
                                version=product.version))
                        match_product.version = product.version

                    # Update version if new version is "more accurate" than the 
                    # one already known
                    elif match_product.version != product.version:
                        if VersionUtils.is_version_more_accurate(
                            old_version=match_product.version, 
                            new_version=product.version):
                            logger.smartsuccess('Version for product ' \
                                '{product} updated: {oldvers} -> {newvers}'.format(
                                    product=product_str,
                                    oldvers=match_product.version,
                                    newvers=product.version))
                            match_product.version = product.version
                        else:
                            logger.smartinfo('Version detected for product ' \
                                '{product}: {newvers}. Not updated in db ' \
                                'because less accurate than {oldvers}'.format(
                                    product=product_str,
                                    newvers=product.version,
                                    oldvers=match_product.version))

                    # Version detected is superior (newer version) to the one in 
                    # db, no update
                    # elif match_product.version < product.version:
                    #     logger.smartsuccess('Version for product ' \
                    #         '{product} detected: {newvers}. Not updated in db ' \
                    #         'because older version {oldvers} already detected'.format(
                    #             product=product_str,
                    #             newvers=product.version,
                    #             oldvers=match_product.version))
                    #     match_product.version = product.version

                    # Same version as already detected
                    else:
                        logger.smartinfo('Product detected: {product} ' \
                            '{version}. Not updated because already in db'.format(
                                product=product_str,
                                version=product.version))

                # Version not detected
                else:
                    logger.smartinfo('Product detected (already in db): ' \
                        '{product}'.format(product=product_str))

                # # Different product name detected
                # else:
                #     oldprod = '{name}{vers}'.format(
                #         name=match_product.name, 
                #         vers=' '+match_product.version if match_product.version else '')
                #     newprod = '{name}{vers}'.format(
                #         name=product.name,
                #         vers=' '+product.version if product.version else '')

                #     logger.smartsuccess('Change product {type}: {oldprod} -> ' \
                #         '{newprod}'.format(
                #             type=product.type,
                #             oldprod=oldprod,
                #             newprod=newprod))
                #     match_product.name = product.name
                #     match_product.version = product.version

            # Type + name not already present in database
            else:

                logger.smartsuccess('New product detected: {product} {version}'.format(
                    product=product_str,
                    version=product.version))
                self.service.products.append(product)


    #------------------------------------------------------------------------------------

    def __update_vulns(self):
        """Update service's vulnerabilities (table "vulns")"""
        for vuln in self.vulns:
            match_vuln = self.service.get_vuln(vuln.name, vuln.reference)
            if match_vuln:
                logger.smartinfo('Detected vulnerability (already in db): {name}'.format(
                    name=vuln.name))
                # Merge with new vuln, i.e. update missing fields if necessary
                match_vuln.merge(vuln)
            else:
                logger.smartsuccess('New vulnerability detected: {name}{ref}'.format(
                    name=vuln.name,
                    ref=' ({})'.format(vuln.reference) if vuln.reference else ''))
                self.service.vulns.append(vuln)


    #------------------------------------------------------------------------------------

    def __update_os(self):
        """Update OS (Service.host.os)"""
        if self.os:
            logger.smartsuccess('Detected OS: {os}'.format(os=self.os))
            self.service.host.os = self.os
            self.service.host.os_vendor = OSUtils.get_os_vendor(self.os)
            self.service.host.os_family = OSUtils.get_os_family(self.os)
            # self.service.host.type = OSUtils.get_device_type(
            #             self.service.host.os,
            #             self.service.host.os_family,
            #             '')


                
