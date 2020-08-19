import os
import re
import time
import docker
import CloudFlare

__author__ = "David Chidell"


class TraefikUpdater:
    def __init__(self):
        self.target_domain = os.environ["TARGET_DOMAIN"]
        excluded = os.environ.get("EXCLUDED_DOMAINS")
        self.cf_email = os.environ.get("CF_EMAIL")
        self.cf_global_key = os.environ.get("CF_GLOBAL_KEY")

        self.cf_token = os.environ.get("CF_TOKEN")

        if self.cf_token is None and (self.cf_global_key is None or self.cf_email is None):
            print("Error: CF_EMAIL and CF_GLOBAL_KEY or CF_TOKEN env vars need setting!")
            exit(1)
        elif self.cf_token is not None and (self.cf_email is not None or self.cf_global_key is not None):
            print("Neither CF_EMAIL or CF_GLOBAL_KEY should be set when using CF_TOKEN (using CF_TOKEN by default)")

        if excluded is None:
            self.excluded_domains = []
        else:
            self.excluded_domains = excluded.split(",")

        self.tld_info = {}
        self.get_domain_vars()

        self.host_pattern = re.compile(r"\`([a-zA-Z0-9\.]+)\`")
        self.dkr = docker.from_env()

    def enter_update_loop(self):
        print("Listening for new containers...")
        t = int(time.time())
        docker_events = self.dkr.events(since=t, filters={"status": "start"}, decode=True)
        for event in docker_events:
            if event.get("status") == "start":
                try:
                    container = self.dkr.containers.get(event.get("id"))
                except docker.errors.NotFound:
                    pass
                else:
                    if container.labels.get("traefik.enable", "False").upper() == "TRUE":
                        print(f"New container online: {container.name}, processing...")
                        self.process_container(container)

    def process_containers(self):
        containers = self.dkr.containers.list(filters={"status": "running", "label": "traefik.enable=true"})
        print(f"Found {len(containers)} existing containers to process")
        for container in containers:
            self.process_container(container)
        print("Finished bulk updating containers!")

    def process_container(self, container):
        for label, value in container.labels.items():
            if "rule" in label and "Host" in value:
                domains = self.host_pattern.findall(value)
                print(f"Found domains: {domains} for container: {container.name}")
                for domain in domains:
                    self.update_domain(domain)

    def update_domain(self, domain):
        dom_split = domain.split(".")
        if len(dom_split) >= 3:
            tld = ".".join(dom_split[1:])
        else:
            tld = domain

        if self.tld_info.get(tld) is None:
            print(f"TLD {tld} not in updatable list")
            return False

        if domain in self.excluded_domains:
            print(f"Domain {domain} has been excluded, skipping...")
            return False    

        dom_info = self.tld_info[tld]
        common_dict = {i: dom_info[i] for i in ("type", "content", "proxied")}
        post_dict = {**{"name": domain}, **common_dict}

        if dom_info["cf_token"] is None:
            cf = CloudFlare.CloudFlare(email=dom_info["cf_email"], token=dom_info["cf_global_key"])
        else:
            cf = CloudFlare.CloudFlare(token=dom_info["cf_token"])

        try:
            get_records = cf.zones.dns_records.get(dom_info["zone"], params={"name": domain})
            if len(get_records) == 0:
                cf.zones.dns_records.post(dom_info["zone"], data=post_dict)
                print(f"New record created: {domain}")
            else:
                for record in get_records:
                    cf.zones.dns_records.put(dom_info["zone"], record["id"], data=post_dict)
                    print(f"Existing record updated: {domain}")

        except CloudFlare.exceptions.CloudFlareAPIError as e:
            print(f"API call failed: {str(e)}")
            return False
        return True

    def get_domain_vars(self):
        tld_count = 0
        self.tld_info = {}
        while True:
            tld_count += 1
            try:
                domain = os.environ[f"DOMAIN{tld_count}"]
                zone = os.environ[f"DOMAIN{tld_count}_ZONE_ID"]
                cf_email = os.environ.get(f"DOMAIN{tld_count}_CF_EMAIL", self.cf_email)
                cf_global_key = os.environ.get(f"DOMAIN{tld_count}_CF_GLOBAL_KEY", self.cf_global_key)
                cf_token = os.environ.get(f"DOMAIN{tld_count}_CF_TOKEN", self.cf_token)

                try:
                    proxied = os.environ.get(f"DOMAIN{tld_count}_PROXIED", "TRUE").upper() == "TRUE"
                except KeyError:
                    proxied = False
                self.tld_info[domain] = {
                    "zone": zone,
                    "proxied": proxied,
                    "type": "CNAME",
                    "content": self.target_domain,
                    "cf_email": cf_email,
                    "cf_global_key": cf_global_key,
                    "cf_token": cf_token,
                }
            except KeyError:
                break
        print(f"Found {tld_count-1} TLDs! {self.tld_info}")
