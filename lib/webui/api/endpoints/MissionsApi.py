#!/usr/bin/env python3
# -*- coding: utf-8 -*-
###
### Web-UI > Backend > Missions REST API
###
import os
from flask import request
from flask_restplus import Resource

from lib.db.Session import Session
from lib.db.Screenshot import ScreenStatus
from lib.db.Service import Protocol
from lib.core.Constants import FilterData
from lib.core.Exceptions import ApiException, ApiNoResultFound
from lib.importer.NmapResultsParser import NmapResultsParser
from lib.requester.Condition import Condition
from lib.requester.Filter import Filter
from lib.requester.JobsRequester import JobsRequester
from lib.requester.MissionsRequester import MissionsRequester
from lib.requester.HostsRequester import HostsRequester
from lib.webui.api.Api import api, settings
from lib.webui.api.Models import Mission, Host, Service, Credential, Product, Vuln
from lib.webui.api.Serializers import mission, host, mission_with_hosts, \
    mission_with_services, mission_with_web, mission_with_options, \
    mission_with_credentials, mission_with_products, mission_with_vulns


ns = api.namespace('missions', description='Operations related to missions')


@ns.route('/')
class MissionListAPI(Resource):

    @ns.doc('list_missions')
    @ns.marshal_list_with(mission)
    def get(self):
        """List all missions"""
        missions = MissionsRequester(Session).get_results()
        # missions_json = []
        # for m in missions:
        #     m_json = api.marshal(m, mission)
        #     m_json['services_count'] = m.get_nb_services()
        #     missions_json.append(m_json)
        # return missions_json
        return list(map(lambda x: Mission(x), missions))


    @ns.doc('create_mission')
    @ns.expect(mission)
    @ns.marshal_with(mission, code=201)
    def post(self):
        """Create a new mission"""
        if 'name' not in request.json:
            raise ApiException('No name has been provided')

        name = request.json['name']
        missions_req = MissionsRequester(Session)
        new_mission = missions_req.add(
            name, 
            request.json['comment'] if 'comment' in request.json else ''
        )
            
        if new_mission:
            return Mission(new_mission)
        else:
            raise ApiException('A mission with the name "{name}" already exists'.format(
                name=name))



@ns.route('/<int:id>')
class MissionAPI(Resource):

    @ns.doc('get_mission')
    @ns.marshal_with(mission)
    def get(self, id):
        """Get a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            return Mission(m)
        else:
            raise ApiNoResultFound()


    @ns.doc('update_mission')
    @ns.expect(mission)
    @ns.marshal_with(mission, code=201)
    def put(self, id):
        """Update a mission name or comment"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            # Rename mission
            if 'name' in request.json:
                if request.json['name'] != m.name:
                    if not missions_req.rename(m.name, request.json['name']):
                        raise ApiException('An error occured when trying to rename ' \
                            'mission "{name}"'.format(name=m.name))

            # Edit comment
            if 'comment' in request.json:
                if request.json['comment'] != m.comment:
                    if not missions_req.edit_comment(request.json['comment']):
                        raise ApiException('An error occured when trying to edit ' \
                            'comment for mission "{name}"'.format(name=m.name))
            return Mission(m)
        else:
            raise ApiNoResultFound()


    @ns.doc('delete_mission')
    def delete(self, id):
        """Delete a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()
        if m:
            if m.name == 'default':
                raise ApiException('Cannot delete "default" mission')

            jobs_req = JobsRequester(Session)
            if jobs_req.is_mission_with_queued_or_running_jobs(id):
                raise ApiException('Impossible to delete the mission because ' \
                    'there is currently a queued/running job targeting it')
            else:
                if missions_req.delete():
                    return None, 201
                else:
                    raise ApiException('An error occured when trying to delete ' \
                        'mission "{name}"'.format(name=m.name))
        else:
            raise ApiNoResultFound()         


@ns.route('/<int:id>/hosts')
class MissionHostsAPI(Resource):

    @ns.doc('list_hosts_in_mission')
    @ns.marshal_with(mission_with_hosts)
    def get(self, id):
        """List all hosts in a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            m = Mission(m)
            m.hosts = list(map(lambda x: Host(x), m.hosts))
            return m
        else:
            raise ApiNoResultFound()


@ns.route('/<int:id>/services')
class MissionServicesAPI(Resource):

    @ns.doc('list_services_in_mission')
    @ns.marshal_with(mission_with_services)
    def get(self, id):
        """List all services in a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            m = Mission(m)
            services_list = list()
            for host in m.hosts:
                for service in host.services:
                    services_list.append(Service(service))
            m.services = services_list
            return m

        else:
            raise ApiNoResultFound()


@ns.route('/<int:id>/web')
class MissionWebAPI(Resource):

    @ns.doc('list_web_in_mission')
    @ns.marshal_with(mission_with_web)
    def get(self, id):
        """List all HTTP services in a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            m = Mission(m)
            services_list = list()
            screenshots_list = list()
            for host in m.hosts:
                for service in host.services:
                    if service.name == 'http':
                        services_list.append(Service(service))
                        
                        if service.screenshot is not None \
                            and service.screenshot.status == ScreenStatus.OK:
                            
                            url = '{base_url}services/{id}/screenshot'.format(
                                base_url=api.base_url,
                                id=service.id)
                            screenshots_list.append({
                                'caption': '{} | {}'.format(
                                    service.url, service.html_title),
                                'source': {
                                    'regular': '{}/large'.format(url),
                                    'thumbnail': '{}/thumb'.format(url)
                                }
                            })

            m.services = services_list
            m.screenshots = screenshots_list
            return m

        else:
            raise ApiNoResultFound()


@ns.route('/<int:id>/credentials')
class MissionCredentialsAPI(Resource):

    @ns.doc('list_credentials_in_mission')
    @ns.marshal_with(mission_with_credentials)
    def get(self, id):
        """List all Credentials in a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            m = Mission(m)
            credentials_list = list()
            for host in m.hosts:
                for svc in host.services:
                    for credential in svc.credentials:
                        credentials_list.append(Credential(credential))
            m.credentials = credentials_list
            return m

        else:
            raise ApiNoResultFound()


@ns.route('/<int:id>/products')
class MissionProductsAPI(Resource):

    @ns.doc('list_products_in_mission')
    @ns.marshal_with(mission_with_products)
    def get(self, id):
        """List all Products in a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            m = Mission(m)
            products_list = list()
            for host in m.hosts:
                for svc in host.services:
                    for product in svc.products:
                        products_list.append(Product(product))
            m.products = products_list
            return m

        else:
            raise ApiNoResultFound()


@ns.route('/<int:id>/vulns')
class MissionVulnsAPI(Resource):

    @ns.doc('list_vulns_in_mission')
    @ns.marshal_with(mission_with_vulns)
    def get(self, id):
        """List all Vulns in a mission"""
        missions_req = MissionsRequester(Session)
        filter_ = Filter()
        filter_.add_condition(Condition(id, FilterData.MISSION_ID))
        missions_req.add_filter(filter_)
        m = missions_req.get_first_result()   
        if m:
            m = Mission(m)
            vulns_list = list()
            for host in m.hosts:
                for svc in host.services:
                    for vuln in svc.vulns:
                        vulns_list.append(Vuln(vuln))
            m.vulns = vulns_list
            return m

        else:
            raise ApiNoResultFound()



@ns.route('/<int:id>/importnmap')
class MissionNmapAPI(Resource):

    @ns.doc('import_nmap')
    def post(self, id):
        """Import services in the mission from Nmap XML Results"""
        if 'file' not in request.files:
            raise ApiException('No file part in the request')
        file = request.files['file']
        if file.filename == '':
            raise ApiException('No file selected for uploading or empty name')
        if file and '.' in file.filename \
                and file.filename.rsplit('.', 1)[1].lower() == 'xml':

            # Check mission is valid
            missions_req = MissionsRequester(Session)
            filter_ = Filter()
            filter_.add_condition(Condition(id, FilterData.MISSION_ID))
            missions_req.add_filter(filter_)
            mission = missions_req.get_first_result()   

            dstpath = os.path.join('/tmp', file.filename)
            try:
                os.remove(dstpath)
            except:
                pass
            file.save(dstpath)

            # Parse Nmap file
            parser = NmapResultsParser(dstpath, settings.services)
            if not parser:
                raise ApiException('Unable to parse file {filename}'.format(
                    file.filename))
                
            results = parser.parse(
                http_recheck=True,
                html_title_grabbing=True,
                nmap_banner_grabbing=False,
                web_technos_detection=True)
            os.remove(dstpath)

            if results is not None:
                if len(results) == 0:
                    print('No new service has been added into current mission')
                else:
                    print('Update the database...')

                    req = HostsRequester(Session)
                    req.select_mission(mission.name)
                    for host in results:
                        req.add_or_merge_host(host)
                    print('Nmap results imported with success into current mission')
            return None, 201


        else:
            raise ApiException('Allowed file type is xml')

# @ns.route('/<int:id>/options')
# class MissionOptionsAPI(Resource):

#     @ns.doc('list_options_in_mission')
#     @ns.marshal_with(mission_with_options)
#     def get(self, id):
#         """List all options in a mission"""
#         missions_req = MissionsRequester(sqlsession)
#         filter_ = Filter()
#         filter_.add_condition(Condition(id, FilterData.MISSION_ID))
#         missions_req.add_filter(filter_)
#         m = missions_req.get_first_result()   
#         if m:
#             m = Mission(m)
#             options_list = list()
#             for host in m.hosts:
#                 for service in host.services:
#                     for option in service.options:
#                         options_list.append(option)
#             m.options = options_list
#             return m

#         else:
#             raise ApiNoResultFound()



