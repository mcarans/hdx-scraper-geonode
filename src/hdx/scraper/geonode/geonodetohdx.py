#!/usr/bin/python
"""
GeoNode Utilities:
-----------------

Reads from GeoNode servers and creates datasets.

"""
import logging
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from urllib.parse import quote_plus

from hdx.data.dataset import Dataset
from hdx.data.organization import Organization
from hdx.data.resource import Resource
from hdx.data.showcase import Showcase
from hdx.location.country import Country
from hdx.utilities import get_uuid
from hdx.utilities.dateparse import default_date, parse_date
from hdx.utilities.downloader import Download
from hdx.utilities.loader import load_yaml
from hdx.utilities.path import script_dir_plus_file
from slugify import slugify

from hdx.scraper.geonode.version import get_geonode_version

logger = logging.getLogger(__name__)


def create_dataset_showcase(
    dataset: Dataset, showcase: Showcase, **kwargs: Any
) -> None:
    """
    Create dataset and showcase

    Args:
        dataset (Dataset): Dataset to create
        showcase (Showcase): Showcase to create
        **kwargs: Args to pass to dataset create_in_hdx call

    Returns:
        None

    """
    dataset.update_from_yaml()
    dataset.create_in_hdx(remove_additional_resources=True, hxl_update=False, **kwargs)
    showcase.create_in_hdx()
    showcase.add_dataset(dataset)


def delete_from_hdx(dataset: Dataset) -> None:
    """
    Delete dataset and any associated showcases

    Args:
        dataset (Dataset): Dataset to delete

    Returns:
        None

    """
    logger.info(f"Deleting {dataset['title']} and any associated showcases")
    for showcase in dataset.get_showcases():
        showcase.delete_from_hdx()
    dataset.delete_from_hdx()


class GeoNodeToHDX:
    """
    Utilities to bring GeoNode data into HDX. hdx_geonode_config_yaml points to a YAML file
    that overrides base values and is in this format:

    ignore_data:
      - deprecated

    category_mapping:
      Elevation: 'elevation - topography - altitude'
      'Inland Waters': river

    titleabstract_mapping:
      bridges:
        - bridges
        - transportation
        - 'facilities and infrastructure'
      idp:
        camp:
          - 'displaced persons locations - camps - shelters'
          - 'internally displaced persons - idp'
        else:
          - 'internally displaced persons - idp'

    Args:
        geonode_url (str): GeoNode server url
        downloader (Download): Download object from HDX Python Utilities
        hdx_geonode_config_yaml (Optional[str]): Configuration file for scraper
    """

    def __init__(
        self,
        geonode_url: str,
        downloader: Download,
        hdx_geonode_config_yaml: Optional[str] = None,
    ) -> None:
        self.geonode_urls = [geonode_url]
        self.downloader = downloader
        base_hdx_geonode_config_yaml = script_dir_plus_file(
            "hdx_geonode.yml", GeoNodeToHDX
        )
        geonode_config = load_yaml(base_hdx_geonode_config_yaml)
        if hdx_geonode_config_yaml is not None:
            geonode_config.update(load_yaml(hdx_geonode_config_yaml))
        self.ignore_data = geonode_config["ignore_data"]
        self.category_mapping = geonode_config["category_mapping"]
        self.titleabstract_mapping = geonode_config["titleabstract_mapping"]

    def get_ignore_data(self) -> List[str]:
        """
        Get terms in the abstract that mean that the dataset should not be added to HDX

        Returns:
            List[str]: List of terms in the abstract that mean that the dataset should not be added to HDX

        """
        return self.ignore_data

    def get_category_mapping(self) -> Dict[str, str]:
        """
        Get mappings from the category field category__gn_description to HDX metadata tags

        Returns:
            Dict[str,str]: List of mappings from the category field category__gn_description to HDX metadata tags

        """
        return self.category_mapping

    def get_titleabstract_mapping(self) -> Dict[str, Union[Dict, List]]:
        """
        Get mappings from terms in the title or abstract to HDX metadata tags

        Returns:
            Dict[str,Union[Dict,List]]: List of mappings from terms in the title or abstract to HDX metadata tags

        """
        return self.titleabstract_mapping

    def get_countries(self, use_count: bool = True) -> List[Dict]:
        """
        Get countries from GeoNode

        Args:
            use_count (bool): Whether to use null count metadata to exclude countries. Defaults to True.

        Returns:
            List[Dict]: List of countries in form (iso3 code, name)

        """
        response = self.downloader.download(f"{self.geonode_urls[0]}/api/regions")
        jsonresponse = response.json()
        countries = list()
        for location in jsonresponse["objects"]:
            loccode = location["code"]
            locname = location["name_en"]
            if use_count:
                count = location.get("count")
                if count is None:
                    logger.info(
                        f"Location {locname} ({loccode}) has nonexistent or null count!"
                    )
                    continue
                if not count:
                    logger.info(
                        f"Location {locname} ({loccode}) has empty or zero count!"
                    )
                    continue
            countryname = Country.get_country_name_from_iso3(loccode)
            if countryname is None:
                logger.info(f"Location {locname} ({loccode}) isn't a country!")
                continue
            countries.append({"iso3": loccode, "name": countryname, "layers": loccode})
        return countries

    def get_layers(self, countryiso: Optional[str] = None) -> List[Dict]:
        """
        Get layers from GeoNode optionally for a particular country

        Args:
            countryiso (Optional[str]): ISO 3 code of country from which to get layers. Defaults to None (all countries).

        Returns:
            List[Dict]: List of layers
        """
        if countryiso is None:
            regionstr = ""
        else:
            regionstr = f"/?regions__code__in={countryiso}"
        response = self.downloader.download(
            f"{self.geonode_urls[0]}/api/layers{regionstr}"
        )
        jsonresponse = response.json()
        return jsonresponse["objects"]

    @staticmethod
    def get_orgname(metadata: Dict, orgclass: Type = Organization) -> str:
        """
        Get orgname from Dict if available or use orgid from Dict to look up organisation name

        Args:
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            orgclass (Type): Class to use for look up. Defaults to Organization.

        Returns:
            str: Organisation name

        """
        orgname = metadata.get("orgname")
        if not orgname:
            organisation = orgclass.read_from_hdx(metadata["orgid"])
            orgname = organisation["name"]
            metadata["orgname"] = orgname
        return orgname

    def generate_dataset_and_showcase(
        self,
        countryiso: str,
        layer: Dict,
        metadata: Dict,
        get_date_from_title: bool = False,
        process_dataset_name: Callable[[str], str] = lambda x: x,
        dataset_tags_mapping: Dict[str, List] = dict(),
    ) -> Tuple[Optional[Dataset], Optional[List], Optional[Showcase]]:
        """
        Generate dataset and showcase for GeoNode layer

        Args:
            countryiso (str): ISO 3 code of country
            layer (Dict): Data about layer from GeoNode
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.
            process_dataset_name (Callable[[str], str]): Function to change the dataset name. Defaults to lambda x: x.
            dataset_tags_mapping (Dict[str, List]): Mapping from dataset name to additional tags. Defaults to empty dictionary.

        Returns:
            Tuple[Optional[Dataset],List,Optional[Showcase]]: Dataset, date ranges in dataset title and Showcase objects or None, None, None
        """
        origtitle = layer["title"].strip()
        notes = layer["abstract"]
        abstract = notes.lower()
        for term in self.ignore_data:
            if term in abstract:
                logger.warning(
                    f"Ignoring {origtitle} as term {term} present in abstract!"
                )
                return None, None, None

        dataset = Dataset({"title": origtitle})
        if get_date_from_title:
            ranges = dataset.remove_dates_from_title(
                change_title=True, set_dataset_date=True
            )
        else:
            ranges = list()
        title = dataset["title"]
        logger.info(f"Creating dataset: {title}")
        detail_url = layer["detail_url"]
        supplemental_information = layer["supplemental_information"]
        if supplemental_information.lower()[:7] == "no info":
            dataset_notes = notes
        else:
            dataset_notes = f"{notes}\n\n{supplemental_information}"
        dataset_date = parse_date(layer["date"])
        if origtitle == title:
            dataset.set_date_of_dataset(dataset_date)
        else:
            dataset_notes = f"{dataset_notes}\n\nOriginal dataset title: {origtitle}"
            logger.info(
                f"Using {ranges[0][0]}-{ranges[0][1]} instead of {dataset_date} for dataset date"
            )
        slugified_name = slugify(f"{self.get_orgname(metadata)}_geonode_{title}")
        slugified_name = process_dataset_name(slugified_name)
        slugified_name = slugified_name[:90]
        dataset["name"] = slugified_name
        dataset["notes"] = dataset_notes
        dataset.set_maintainer(metadata["maintainerid"])
        dataset.set_organization(metadata["orgid"])
        updatefreq = metadata.get("updatefreq", "As needed")
        dataset.set_expected_update_frequency(updatefreq)
        subnational = metadata.get("subnational", True)
        dataset.set_subnational(subnational)
        dataset.add_country_location(countryiso)
        tags = dataset_tags_mapping.get(slugified_name, list())
        tags.append("geodata")
        tag = layer["category__gn_description"]
        if tag is not None:
            if tag in self.category_mapping:
                tag = self.category_mapping[tag]
            tags.append(tag)
        title_abstract = f"{title} {notes}".lower()
        for key in self.titleabstract_mapping:
            if key in title_abstract:
                mapping = self.titleabstract_mapping[key]
                if isinstance(mapping, list):
                    tags.extend(mapping)
                elif isinstance(mapping, dict):
                    found = False
                    for subkey in mapping:
                        if subkey == "else":
                            continue
                        if subkey in title_abstract:
                            tags.extend(mapping[subkey])
                            found = True
                    if not found and "else" in mapping:
                        tags.extend(mapping["else"])
        dataset.add_tags(tags)
        srid = quote_plus(layer["srid"])
        if "%3Ageonode%3A" in detail_url:
            geonode_url = (
                f"https://{detail_url.rsplit('/', 1)[-1].split('%3Ageonode%3A')[0]}"
            )
            if geonode_url not in self.geonode_urls:
                self.geonode_urls.append(geonode_url)
        else:
            geonode_url = self.geonode_urls[0]
        typename = f"geonode:{detail_url.rsplit('geonode%3A', 1)[-1]}"
        resource = Resource(
            {
                "name": f"{title} shapefile",
                "url": f"{geonode_url}/geoserver/wfs?format_options=charset:UTF-8&typename={typename}&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature",
                "description": f"Zipped Shapefile. {notes}",
            }
        )
        resource.set_file_type("zipped shapefile")
        dataset.add_update_resource(resource)
        resource = Resource(
            {
                "name": f"{title} geojson",
                "url": f"{geonode_url}/geoserver/wfs?srsName={srid}&typename={typename}&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature",
                "description": f"GeoJSON file. {notes}",
            }
        )
        resource.set_file_type("GeoJSON")
        dataset.add_update_resource(resource)

        showcase = Showcase(
            {
                "name": f"{slugified_name}-showcase",
                "title": title,
                "notes": notes,
                "url": f"{self.geonode_urls[0]}{detail_url}",
                "image_url": layer["thumbnail_url"],
            }
        )
        showcase.add_tags(tags)
        return dataset, ranges, showcase

    def generate_datasets_and_showcases(
        self,
        metadata: Dict,
        create_dataset_showcase: Callable[
            [Dataset, Showcase, Any], None
        ] = create_dataset_showcase,
        countrydata: Dict[str, Optional[str]] = None,
        get_date_from_title: bool = False,
        process_dataset_name: Callable[[str], str] = lambda x: x,
        dataset_tags_mapping: Dict[str, List] = dict(),
        **kwargs: Any,
    ) -> List[str]:
        """
        Generate datasets and showcases for all GeoNode layers

        Args:
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            create_dataset_showcase (Callable[[Dataset, Showcase, Any], None]): Function to call to create dataset and showcase
            countrydata (Dict[str, Optional[str]]): Dictionary of countrydata. Defaults to None (read from GeoNode).
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.
            process_dataset_name (Callable[[str], str]): Function to change the dataset name. Defaults to lambda x: x.
            dataset_tags_mapping (Dict[str, List]): Mapping from dataset name to additional tags. Defaults to empty dictionary.
            **kwargs: Args to pass to dataset create_in_hdx call

        Returns:
            List[str]: List of names of datasets added or updated

        """
        logger.info("--------------------------------------------------")
        logger.info(f"> Using HDX Python GeoNode Library {get_geonode_version()}")
        if countrydata:
            countries = [countrydata]
        else:
            countries = self.get_countries()
            logger.info(f"Number of countries: {len(countries)}")
        dataset_dates = OrderedDict()
        if "batch" not in kwargs:
            kwargs["batch"] = get_uuid()
        for countrydata in countries:
            layers = self.get_layers(countrydata["layers"])
            logger.info(
                f'Number of datasets to upload in {countrydata["name"]}: {len(layers)}'
            )
            for layer in layers:
                dataset, ranges, showcase = self.generate_dataset_and_showcase(
                    countrydata["iso3"],
                    layer,
                    metadata,
                    get_date_from_title,
                    process_dataset_name,
                    dataset_tags_mapping=dataset_tags_mapping,
                )
                if dataset:
                    dataset_name = dataset["name"]
                    max_date = default_date
                    for range in ranges:
                        if range[1] > max_date:
                            max_date = range[1]
                    prev_max = dataset_dates.get(dataset_name)
                    if prev_max and prev_max > max_date:
                        logger.warning(
                            f'Ignoring {layer["title"]} with max date {max_date}!'
                            f" {dataset_name} (dates removed) with max date {prev_max} has been created already!"
                        )
                        continue
                    create_dataset_showcase(dataset, showcase, **kwargs)
                    dataset_dates[dataset_name] = max_date
        return list(dataset_dates.keys())

    def delete_other_datasets(
        self,
        datasets_to_keep: List[str],
        metadata: Dict,
        delete_from_hdx: Callable[[Dataset], None] = delete_from_hdx,
    ) -> None:
        """
        Delete all GeoNode datasets and associated showcases in HDX where layers have been deleted from
        the GeoNode server.

        Args:
            datasets_to_keep (List[str]): List of dataset names that are to be kept (they were added or updated)
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            delete_from_hdx (Callable[[Dataset], None]): Function to call to delete dataset

        Returns:
            None

        """
        for dataset in Dataset.search_in_hdx(
            fq=f"organization:{self.get_orgname(metadata)}"
        ):
            if dataset["maintainer"] != metadata["maintainerid"]:
                continue
            if dataset["name"] in datasets_to_keep:
                continue
            if not any(x in dataset.get_resource()["url"] for x in self.geonode_urls):
                continue
            logger.info(f"Deleting {dataset['title']}")
            delete_from_hdx(dataset)
