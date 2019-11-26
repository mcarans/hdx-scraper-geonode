# -*- coding: UTF-8 -*-
"""Geonode scraper Tests"""
import copy
from os.path import join

import pytest
from hdx.data.dataset import Dataset
from hdx.data.vocabulary import Vocabulary
from hdx.hdx_configuration import Configuration
from hdx.hdx_locations import Locations
from hdx.location.country import Country

from hdx.scraper.geonode.geonodetohdx import GeoNodeToHDX


class TestGeoNodeToHDX:
    wfplocationsdata = [{'code': 'SAF', 'count': 2, 'id': 14, 'level': 2, 'lft': 65, 'name': 'Southern Africa',
                         'name_en': 'Southern Africa', 'resource_uri': '/api/regions/14/', 'rght': 82, 'tree_id': 90},
                        {'code': 'SDN', 'count': 33, 'id': 218, 'level': 3, 'lft': 58, 'name': 'Sudan',
                         'name_en': 'Sudan', 'resource_uri': '/api/regions/218/', 'rght': 59, 'tree_id': 90},
                        {'code': 'ALB', 'count': 0, 'id': 19, 'level': 2, 'lft': 321, 'name': 'Albania',
                         'name_en': 'Albania', 'resource_uri': '/api/regions/19/', 'rght': 322, 'tree_id': 90},
                        {'code': 'YEM', 'count': None, 'id': 251, 'level': 2, 'lft': 491, 'name': 'Yemen',
                         'name_en': 'Yemen', 'resource_uri': '/api/regions/251/', 'rght': 492, 'tree_id': 90}]

    mimulayersdata = [{'abstract': 'Towns are urban areas divided into wards.', 'category__gn_description': 'Location',
                       'csw_type': 'dataset', 'csw_wkt_geometry': 'POLYGON(456)', 'date': '2019-08-05T22:06:00',
                       'detail_url': '/layers/geonode%3Ammr_town_2019_july', 'distribution_description': 'Web address (URL)',
                       'distribution_url': 'http://geonode.themimu.info/layers/geonode%3Ammr_town_2019_july', 'id': 211,
                       'owner__username': 'phyokyi', 'popular_count': 126, 'rating': 0, 'share_count': 0, 'srid': 'EPSG:4326',
                       'supplemental_information': 'Place name from GAD, transliteration by MIMU. Names available in Myanmar Unicode 3 and Roman script.',
                       'thumbnail_url': 'http://geonode.themimu.info/uploaded/thumbs/layer-3bc1761a-b7f7-11e9-9231-42010a80000c-thumb.png',
                       'title': 'Myanmar Town 2019 July', 'uuid': '3bc1761a-b7f7-11e9-9231-42010a80000c'},
                      {'abstract': 'A Landsat-based classification of Myanmar’s forest cover',
                       'category__gn_description': None, 'csw_type': 'dataset', 'csw_wkt_geometry': 'POLYGON(567)', 'date': '2019-02-12T11:12:00',
                       'detail_url': '/layers/geonode%3Amyan_lvl2_smoothed_dec2015_resamp', 'distribution_description': 'Web address (URL)',
                       'distribution_url': 'http://geonode.themimu.info/layers/geonode%3Amyan_lvl2_smoothed_dec2015_resamp',
                       'id': 173, 'owner__username': 'EcoDev-ALARM', 'popular_count': 749, 'rating': 0, 'share_count': 0,
                       'srid': 'EPSG:4326', 'supplemental_information': 'LAND COVER CLASSES',
                       'thumbnail_url': 'http://geonode.themimu.info/uploaded/thumbs/layer-5801f3fa-2ee9-11e9-8d0e-42010a80000c-thumb.png',
                       'title': 'Myanmar 2002-2014 Forest Cover Change', 'uuid': '5801f3fa-2ee9-11e9-8d0e-42010a80000c'}]

    wfplayersdata = [{'abstract': 'This layer contains...', 'category__gn_description': 'Physical Features, Land Cover, Land Use, DEM',
                      'csw_type': 'dataset',  'csw_wkt_geometry': 'POLYGON(456)', 'date': '2018-11-22T16:56:00',
                      'detail_url': '/layers/geonode%3Asdn_ica_landdegradation_geonode_20180201', 'distribution_description': 'Web address (URL)',
                      'distribution_url': 'https://geonode.wfp.org/layers/geonode%3Asdn_ica_landdegradation_geonode_20180201',
                      'id': 9110, 'owner__username': 'stefano.cairo', 'popular_count': 223, 'rating': 0, 'share_count': 0, 'srid': 'EPSG:4326',
                      'supplemental_information': 'No information provided',
                      'thumbnail_url': 'https://geonode.wfp.org/uploaded/thumbs/layer-3c418668-ee6f-11e8-81a9-005056822e38-thumb.png',
                      'title': 'ICA Sudan, 2018 - Land Degradation, 2001-2013', 'uuid': '3c418668-ee6f-11e8-81a9-005056822e38'},
                     {'abstract': 'This layer contains...', 'category__gn_description': 'Physical Features, Land Cover, Land Use, DEM',
                      'csw_type': 'dataset', 'csw_wkt_geometry': 'POLYGON(567)', 'date': '2018-11-22T16:18:00',
                      'detail_url': '/layers/geonode%3Asdn_ica_predlhz_geonode_20180201', 'distribution_description': 'Web address (URL)',
                      'distribution_url': 'https://geonode.wfp.org/layers/geonode%3Asdn_ica_predlhz_geonode_20180201',
                      'id': 9108, 'owner__username': 'stefano.cairo', 'popular_count': 208, 'rating': 0, 'share_count': 0, 'srid': 'EPSG:4326',
                      'supplemental_information': 'No information provided',
                      'thumbnail_url': 'https://geonode.wfp.org/uploaded/thumbs/layer-e4cc9008-ee69-11e8-a005-005056822e38-thumb.png',
                      'title': 'ICA Sudan, 2018 - Most Predominant Livelihood Zones, 2014', 'uuid': 'e4cc9008-ee69-11e8-a005-005056822e38'}]

    wfpdatasets = [{'name': 'wfp-geonode-sdn-ica-landdegradation-geonode', 'title': 'ICA Sudan, 2018 - Land Degradation, 2001-2013',
                    'notes': 'This layer contains...', 'maintainer': 'd7a13725-5cb5-48f4-87ac-a70b5cea531e', 'owner_org': '3ecac442-7fed-448d-8f78-b385ef6f84e7',
                    'dataset_date': '11/22/2018', 'data_update_frequency': '-2', 'subnational': '1', 'groups': [{'name': 'sdn'}],
                    'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'land use and land cover', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]},
                   {'name': 'wfp-geonode-sdn-ica-predlhz-geonode', 'title': 'ICA Sudan, 2018 - Most Predominant Livelihood Zones, 2014',
                    'notes': 'This layer contains...', 'maintainer': 'd7a13725-5cb5-48f4-87ac-a70b5cea531e', 'owner_org': '3ecac442-7fed-448d-8f78-b385ef6f84e7',
                    'dataset_date': '11/22/2018', 'data_update_frequency': '-2', 'subnational': '1', 'groups': [{'name': 'sdn'}],
                    'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'land use and land cover', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}]

    wfpresources = [[{'name': 'ICA Sudan, 2018 - Land Degradation, 2001-2013 shapefile',
                      'url': 'http://xxx/geoserver/wfs?format_options=charset:UTF-8&typename=geonode%3Asdn_ica_landdegradation_geonode_20180201&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature',
                      'description': 'Zipped Shapefile. This layer contains...', 'format': 'zipped shapefile',
                      'resource_type': 'api', 'url_type': 'api'},
                     {'name': 'ICA Sudan, 2018 - Land Degradation, 2001-2013 geojson',
                      'url': 'http://xxx/geoserver/wfs?srsName=EPSG%3A4326&typename=geonode%3Asdn_ica_landdegradation_geonode_20180201&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature',
                      'description': 'GeoJSON file. This layer contains...', 'format': 'geojson',
                      'resource_type': 'api', 'url_type': 'api'}],
                    [{'name': 'ICA Sudan, 2018 - Most Predominant Livelihood Zones, 2014 shapefile',
                      'url': 'http://xxx/geoserver/wfs?format_options=charset:UTF-8&typename=geonode%3Asdn_ica_predlhz_geonode_20180201&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature',
                      'description': 'Zipped Shapefile. This layer contains...', 'format': 'zipped shapefile',
                      'resource_type': 'api', 'url_type': 'api'},
                     {'name': 'ICA Sudan, 2018 - Most Predominant Livelihood Zones, 2014 geojson',
                      'url': 'http://xxx/geoserver/wfs?srsName=EPSG%3A4326&typename=geonode%3Asdn_ica_predlhz_geonode_20180201&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature',
                      'description': 'GeoJSON file. This layer contains...', 'format': 'geojson',
                      'resource_type': 'api', 'url_type': 'api'}]]

    wfporganization = {'description': "WFP is the world's largest humanitarian agency fighting hunger worldwide...", 'created': '2014-10-24T15:55:52.696098',
                       'title': 'WFP - World Food Programme', 'name': 'wfp', 'is_organization': True, 'state': 'active', 'image_url': '',
                       'revision_id': 'befd2a5c-7eff-4897-b459-80b00efbf678', 'type': 'organization', 'id': '3ecac442-7fed-448d-8f78-b385ef6f84e7', 'approval_status': 'approved'}

    wfpshowcases = [{'name': 'wfp-geonode-sdn-ica-landdegradation-geonode-showcase', 'title': 'ICA Sudan, 2018 - Land Degradation, 2001-2013',
                     'notes': 'This layer contains...', 'url': 'http://xxx/layers/geonode%3Asdn_ica_landdegradation_geonode_20180201',
                     'image_url': 'https://geonode.wfp.org/uploaded/thumbs/layer-3c418668-ee6f-11e8-81a9-005056822e38-thumb.png',
                     'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'land use and land cover', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]},
                    {'name': 'wfp-geonode-sdn-ica-predlhz-geonode-showcase', 'title': 'ICA Sudan, 2018 - Most Predominant Livelihood Zones, 2014',
                     'notes': 'This layer contains...', 'url': 'http://xxx/layers/geonode%3Asdn_ica_predlhz_geonode_20180201',
                     'image_url': 'https://geonode.wfp.org/uploaded/thumbs/layer-e4cc9008-ee69-11e8-a005-005056822e38-thumb.png',
                     'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'land use and land cover', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}]

    mimudatasets = [{'name': 'mimu-geonode-mmr-town-2019-july', 'title': 'Myanmar Town 2019 July',
                     'notes': 'Towns are urban areas divided into wards.\n\nPlace name from GAD, transliteration by MIMU. Names available in Myanmar Unicode 3 and Roman script.',
                     'maintainer': '196196be-6037-4488-8b71-d786adf4c081', 'owner_org': 'bde18602-2e92-462a-8e88-a0018a7b13f9',
                     'dataset_date': '08/05/2019', 'data_update_frequency': '-2', 'subnational': '1', 'groups': [{'name': 'mmr'}],
                     'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'populated places - settlements', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]},
                    {'name': 'mimu-geonode-myan-lvl2-smoothed-dec2015-resamp', 'title': 'Myanmar 2002-2014 Forest Cover Change',
                     'notes': 'A Landsat-based classification of Myanmar’s forest cover\n\nLAND COVER CLASSES',
                     'maintainer': '196196be-6037-4488-8b71-d786adf4c081', 'owner_org': 'bde18602-2e92-462a-8e88-a0018a7b13f9',
                     'dataset_date': '02/12/2019', 'data_update_frequency': '-2', 'subnational': '1', 'groups': [{'name': 'mmr'}],
                     'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'land use and land cover', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}]

    mimuresources = [[{'name': 'Myanmar Town 2019 July shapefile',
                       'url': 'http://yyy/geoserver/wfs?format_options=charset:UTF-8&typename=geonode%3Ammr_town_2019_july&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature',
                       'description': 'Zipped Shapefile. Towns are urban areas divided into wards.',
                       'format': 'zipped shapefile', 'resource_type': 'api', 'url_type': 'api'},
                      {'name': 'Myanmar Town 2019 July geojson',
                       'url': 'http://yyy/geoserver/wfs?srsName=EPSG%3A4326&typename=geonode%3Ammr_town_2019_july&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature',
                       'description': 'GeoJSON file. Towns are urban areas divided into wards.',
                       'format': 'geojson', 'resource_type': 'api', 'url_type': 'api'}],
                     [{'name': 'Myanmar 2002-2014 Forest Cover Change shapefile',
                       'url': 'http://yyy/geoserver/wfs?format_options=charset:UTF-8&typename=geonode%3Amyan_lvl2_smoothed_dec2015_resamp&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature',
                       'description': 'Zipped Shapefile. A Landsat-based classification of Myanmar’s forest cover',
                       'format': 'zipped shapefile', 'resource_type': 'api', 'url_type': 'api'},
                      {'name': 'Myanmar 2002-2014 Forest Cover Change geojson',
                       'url': 'http://yyy/geoserver/wfs?srsName=EPSG%3A4326&typename=geonode%3Amyan_lvl2_smoothed_dec2015_resamp&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature',
                       'description': 'GeoJSON file. A Landsat-based classification of Myanmar’s forest cover',
                       'format': 'geojson', 'resource_type': 'api', 'url_type': 'api'}]]

    mimuorganization = {'description': 'The Myanmar Information Management Unit / MIMU is a service to the UN Country Team and Humanitarian Country Team...',
                        'created': '2015-12-09T09:21:45.264734', 'title': 'Myanmar Information Management Unit (MIMU)', 'name': 'mimu', 'is_organization': True, 'state': 'active',
                        'image_url': '', 'revision_id': '7e5161d3-fdd6-4436-ba04-1a65740e21e0', 'type': 'organization', 'id': 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'approval_status': 'approved'}

    mimushowcases = [{'name': 'mimu-geonode-mmr-town-2019-july-showcase', 'title': 'Myanmar Town 2019 July',
                      'notes': 'Towns are urban areas divided into wards.', 'url': 'http://yyy/layers/geonode%3Ammr_town_2019_july',
                      'image_url': 'http://geonode.themimu.info/uploaded/thumbs/layer-3bc1761a-b7f7-11e9-9231-42010a80000c-thumb.png',
                      'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'populated places - settlements', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]},
                     {'name': 'mimu-geonode-myan-lvl2-smoothed-dec2015-resamp-showcase', 'title': 'Myanmar 2002-2014 Forest Cover Change',
                      'notes': 'A Landsat-based classification of Myanmar’s forest cover', 'url': 'http://yyy/layers/geonode%3Amyan_lvl2_smoothed_dec2015_resamp',
                      'image_url': 'http://geonode.themimu.info/uploaded/thumbs/layer-5801f3fa-2ee9-11e9-8d0e-42010a80000c-thumb.png',
                      'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'land use and land cover', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}]

    @staticmethod
    def construct_dataset(origdata, origresources, maintainer=None, orgid=None, organization=None):
        dataset = Dataset(copy.deepcopy(origdata))
        if maintainer:
            dataset['maintainer'] = maintainer
        if orgid:
            dataset['owner_org'] = orgid
        if organization:
            dataset['organization'] = organization
        dataset.add_update_resources(copy.deepcopy(origresources))
        return dataset

    @pytest.fixture(scope='function')
    def configuration(self):
        Configuration._create(hdx_read_only=True, user_agent='test',
                              project_config_yaml=join('tests', 'config', 'project_configuration.yml'))
        Locations.set_validlocations([{'name': 'mmr', 'title': 'Myanmar'}, {'name': 'sdn', 'title': 'Sudan'}, {'name': 'alb', 'title': 'Albania'}, {'name': 'yem', 'title': 'Yemen'}])  # add locations used in tests
        Country.countriesdata(False)
        Vocabulary._tags_dict = True
        Vocabulary._approved_vocabulary = {
            'tags': [{'name': 'geodata'}, {'name': 'populated places - settlements'}, {'name': 'land use and land cover'}, {'name': 'erosion'}, {'name': 'landslides - mudslides'}, {'name': 'floods - storm surges'}, {'name': 'droughts'}, {'name': 'food assistance'}, {'name': 'hazards and risk'}, {'name': 'administrative divisions'}, {'name': 'food security'}, {'name': 'security'}, {'name': 'displaced persons locations - camps - shelters'}, {'name': 'refugees'}, {'name': 'internally displaced persons - idp'}, {'name': 'malnutrition'}, {'name': 'nutrition'}, {'name': 'food assistance'}, {'name': 'roads'}, {'name': 'transportation'}, {'name': 'aviation'}, {'name': 'facilities and infrastructure'}, {'name': 'bridges'}, {'name': 'transportation'}, {'name': 'facilities and infrastructure'}, {'name': 'cold waves'}, {'name': 'cash assistance'}, {'name': 'acronyms'}],
            'id': '4e61d464-4943-4e97-973a-84673c1aaa87', 'name': 'approved'}

    @pytest.fixture(scope='function')
    def downloader(self):
        class Response:
            @staticmethod
            def json():
                pass

        class Download:
            @staticmethod
            def download(url):
                response = Response()
                if url == 'http://xxx/api/regions':
                    def fn():
                        return {'objects': TestGeoNodeToHDX.wfplocationsdata}

                    response.json = fn
                elif url == 'http://xxx/api/layers/?regions__code__in=SDN':
                    def fn():
                        return {'objects': TestGeoNodeToHDX.wfplayersdata}
                    response.json = fn
                elif url == 'http://yyy/api/layers':
                    def fn():
                        return {'objects': TestGeoNodeToHDX.mimulayersdata}

                    response.json = fn
                return response

        return Download()

    @pytest.fixture(scope='function')
    def yaml_config(self):
        return join('tests', 'fixtures', 'hdx_geonode.yml')

    @pytest.fixture(scope='function')
    def search_datasets(self, monkeypatch):

        def search_in_hdx(fq):
            if 'wfp' in fq:
                return [self.construct_dataset(dataset, resources) for dataset, resources in
                        zip((self.wfpdatasets + self.mimudatasets), (self.wfpresources+self.mimuresources))]
            else:
                return [self.construct_dataset(dataset, resources, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9') for dataset, resources in
                        zip((self.wfpdatasets + self.mimudatasets), (self.wfpresources + self.mimuresources))]

        monkeypatch.setattr(Dataset, 'search_in_hdx', staticmethod(search_in_hdx))

    def test_get_countries(self, configuration, downloader):
        geonodetohdx = GeoNodeToHDX('http://xxx', downloader)
        countries = geonodetohdx.get_countries()
        assert countries == [{'iso3': 'SDN', 'name': 'Sudan', 'layers': 'SDN'}]
        countries = geonodetohdx.get_countries(use_count=False)
        assert countries == [{'iso3': 'SDN', 'name': 'Sudan', 'layers': 'SDN'}, {'iso3': 'ALB', 'name': 'Albania', 'layers': 'ALB'}, {'iso3': 'YEM', 'name': 'Yemen', 'layers': 'YEM'}]

    def test_get_layers(self, downloader):
        geonodetohdx = GeoNodeToHDX('http://xxx', downloader)
        layers = geonodetohdx.get_layers(countryiso='SDN')
        assert layers == TestGeoNodeToHDX.wfplayersdata
        geonodetohdx = GeoNodeToHDX('http://yyy', downloader)
        layers = geonodetohdx.get_layers()
        assert layers == TestGeoNodeToHDX.mimulayersdata

    def test_generate_dataset_and_showcase(self, configuration, downloader):
        geonodetohdx = GeoNodeToHDX('http://xxx', downloader)
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('SDN', TestGeoNodeToHDX.wfplayersdata[0], 'd7a13725-5cb5-48f4-87ac-a70b5cea531e', '3ecac442-7fed-448d-8f78-b385ef6f84e7', 'WFP')
        assert dataset == self.wfpdatasets[0]
        resources = dataset.get_resources()
        assert resources == self.wfpresources[0]
        assert showcase == self.wfpshowcases[0]

        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('SDN', TestGeoNodeToHDX.wfplayersdata[1], 'd7a13725-5cb5-48f4-87ac-a70b5cea531e', '3ecac442-7fed-448d-8f78-b385ef6f84e7', 'WFP')
        assert dataset == self.wfpdatasets[1]
        resources = dataset.get_resources()
        assert resources == self.wfpresources[1]
        assert showcase == self.wfpshowcases[1]

        geonodetohdx = GeoNodeToHDX('http://yyy', downloader)
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', TestGeoNodeToHDX.mimulayersdata[0], '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset == self.mimudatasets[0]
        resources = dataset.get_resources()
        assert resources == self.mimuresources[0]
        assert showcase == self.mimushowcases[0]

        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', TestGeoNodeToHDX.mimulayersdata[1], '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset == self.mimudatasets[1]
        resources = dataset.get_resources()
        assert resources == self.mimuresources[1]
        assert showcase == self.mimushowcases[1]

    def test_mappings(self, configuration, downloader, yaml_config):
        geonodetohdx = GeoNodeToHDX('http://yyy', downloader)
        layersdata = copy.deepcopy(TestGeoNodeToHDX.mimulayersdata[0])
        abstract = layersdata['abstract']
        layersdata['abstract'] = '%s deprecated' % abstract
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', layersdata, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset is None
        assert showcase is None
        geonodetohdx = GeoNodeToHDX('http://yyy', downloader, yaml_config)
        layersdata['abstract'] = '%s deprecated' % abstract
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', layersdata, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset is not None
        assert showcase is not None
        layersdata['abstract'] = '%s abcd' % abstract
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', layersdata, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset is None
        assert showcase is None
        layersdata['abstract'] = '%s hdx' % abstract
        geonodetohdx.get_ignore_data().append('hdx')
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', layersdata, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset is None
        assert showcase is None
        geonodetohdx.get_category_mapping()['Location'] = 'acronyms'
        geonodetohdx.get_titleabstract_mapping()['ffa'] = ['cash assistance']
        layersdata['abstract'] = '%s landslide flood drought ffa emergency levels admin boundaries food security refugee camp idp malnutrition food distribution streets airport bridges frost erosion' % abstract
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', layersdata, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset == {'name': 'mimu-geonode-mmr-town-2019-july',
                           'title': 'Myanmar Town 2019 July',
                           'notes': 'Towns are urban areas divided into wards. landslide flood drought ffa emergency levels admin boundaries food security refugee camp idp malnutrition food distribution streets airport bridges frost erosion\n\nPlace name from GAD, transliteration by MIMU. Names available in Myanmar Unicode 3 and Roman script.',
                           'maintainer': '196196be-6037-4488-8b71-d786adf4c081', 'owner_org': 'bde18602-2e92-462a-8e88-a0018a7b13f9',
                           'dataset_date': '08/05/2019', 'data_update_frequency': '-2', 'subnational': '1', 'groups': [{'name': 'mmr'}],
                           'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'acronyms', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'landslides - mudslides', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'floods - storm surges', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'droughts', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'hazards and risk', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'food assistance', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'cold waves', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'erosion', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'roads', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'transportation', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'aviation', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'facilities and infrastructure', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'bridges', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'administrative divisions', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'food security', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'displaced persons locations - camps - shelters', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'refugees', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'internally displaced persons - idp', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'malnutrition', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'cash assistance', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}
        layersdata['abstract'] = '%s security nutrition' % abstract
        dataset, showcase = geonodetohdx.generate_dataset_and_showcase('MMR', layersdata, '196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU')
        assert dataset == {'name': 'mimu-geonode-mmr-town-2019-july',
                           'title': 'Myanmar Town 2019 July',
                           'notes': 'Towns are urban areas divided into wards. security nutrition\n\nPlace name from GAD, transliteration by MIMU. Names available in Myanmar Unicode 3 and Roman script.',
                           'maintainer': '196196be-6037-4488-8b71-d786adf4c081', 'owner_org': 'bde18602-2e92-462a-8e88-a0018a7b13f9',
                           'dataset_date': '08/05/2019', 'data_update_frequency': '-2', 'subnational': '1', 'groups': [{'name': 'mmr'}],
                           'tags': [{'name': 'geodata', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'acronyms', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'},
                                    {'name': 'security', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}, {'name': 'nutrition', 'vocabulary_id': '4e61d464-4943-4e97-973a-84673c1aaa87'}]}

    def test_generate_datasets_and_showcases(self, configuration, downloader):
        geonodetohdx = GeoNodeToHDX('http://xxx', downloader)
        datasets = list()
        showcases = list()

        def create_dataset_showcase(dataset, showcase):
            datasets.append(dataset)
            showcases.append(showcase)

        datasets_to_keep = geonodetohdx.generate_datasets_and_showcases('d7a13725-5cb5-48f4-87ac-a70b5cea531e', '3ecac442-7fed-448d-8f78-b385ef6f84e7', 'WFP',
                                                                        create_dataset_showcase=create_dataset_showcase)
        assert datasets == self.wfpdatasets
        assert showcases == self.wfpshowcases
        assert datasets_to_keep == datasets

        geonodetohdx = GeoNodeToHDX('http://yyy', downloader)
        datasets = list()
        showcases = list()
        datasets_to_keep = geonodetohdx.generate_datasets_and_showcases('196196be-6037-4488-8b71-d786adf4c081', 'bde18602-2e92-462a-8e88-a0018a7b13f9', 'MIMU',
                                                                        create_dataset_showcase=create_dataset_showcase, countrydata={'iso3': 'MMR', 'name': 'Myanmar', 'layers': None})
        assert datasets == self.mimudatasets
        assert showcases == self.mimushowcases
        assert datasets_to_keep == datasets

    def test_delete_other_datasets(self, search_datasets, configuration, downloader):
        datasets = list()

        def delete_from_hdx(dataset):
            datasets.append(dataset)

        wfpdatasets = [self.construct_dataset(dataset, resources, organization=self.wfporganization)
                       for dataset, resources in zip(self.wfpdatasets, self.wfpresources)]
        geonodetohdx = GeoNodeToHDX('http://xxx', downloader)
        geonodetohdx.delete_other_datasets(wfpdatasets, delete_from_hdx=delete_from_hdx)
        assert len(datasets) == 0

        mimudatasets = [self.construct_dataset(dataset, resources, organization=self.mimuorganization)
                        for dataset, resources in zip(self.mimudatasets, self.mimuresources)]
        geonodetohdx.delete_other_datasets(mimudatasets, delete_from_hdx=delete_from_hdx)
        assert datasets[0]['name'] == self.wfpdatasets[0]['name']
        assert datasets[1]['name'] == self.wfpdatasets[1]['name']
        geonodetohdx = GeoNodeToHDX('http://yyy', downloader)
        datasets = list()
        geonodetohdx.delete_other_datasets(mimudatasets, delete_from_hdx=delete_from_hdx)
        assert len(datasets) == 0
