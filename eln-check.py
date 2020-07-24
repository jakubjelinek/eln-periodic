#!/usr/bin/python3

import argparse
import logging
import os
import re
import rpm

import koji

rawhide = "f33"

# Connect to Fedora Koji instance
session = koji.ClientSession('https://koji.fedoraproject.org/kojihub')

def get_eln_builds():
    return session.listTagged("eln", latest=True) 

def no_dist_nvr(build):
    nvr = build['nvr']
    return nvr.rsplit(".", 1)[0]

def evr(build):
    if build['epoch']:
        epoch = str(build['epoch'])
    else:
        epoch = "0"
    version = build['version']
    p = re.compile(".(fc|eln)[0-9]*")              
    release = re.sub(p, "", build['release'])
    return (epoch, version, release)

def is_higher(evr1, evr2):
    return (rpm.labelCompare(evr1, evr2) > 0)
    
def get_build(package, tag):
    builds = session.listTagged(tag, package=package, latest=True)
    if builds:
        return builds[0]
    else:
        return None

def is_excluded(package):
    """
    Return True if package is excluded from rebuild automation.
    """

    excludes = [
        "kernel",
    ]
    exclude_prefix = [
        "ghc-",
    ]

    if package in excludes:
        return True
    for prefix in exclude_prefix:
        if package.startswith(prefix):
            return True
    return False
    
def diff_with_rawhide(package, eln_build=None):
    """Compares version of ELN and Rawhide packages. If eln_build is not known,
    fetches the latest ELN build from Koji.

    If there is a difference, return tuple (package, rawhide_build, eln_build),
    else return None.
    """

    if not eln_build:
        eln_build = get_build(package, "eln")

    rawhide_build = get_build(package, rawhide)

    if not eln_build:
        logging.debug("No build found for {0} in ELN".format(package))
        return (package, rawhide_build, None)
            
    logging.debug("Checking {0}".format(eln_build))

    if is_higher(evr(rawhide_build), evr(eln_build)):
        return (package, rawhide_build, eln_build)
    
    return None
 

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    
    parser.add_argument("-v", "--verbose",
                        help="Enable debug logging",
                        action='store_true',
    )
    parser.add_argument("-o", "--output",
                        help="Filepath for the output",
                        default="rebuild.txt"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    eln_builds = get_eln_builds()

    counter = 0

    f = open(args.output,'w')

    for eln_build in eln_builds:
        diff = diff_with_rawhide(package=eln_build['name'], eln_build=eln_build)
        if diff:
            counter += 1
            logging.info("Difference found: {0} {1}".format(diff[1]['nvr'], diff[2]['nvr']))
            if is_excluded(diff[0]):
                logging.warning("Skipping as excluded")
                continue
            
            f.write("{0}\n".format(diff[1]['build_id']))

    f.close()

    logging.info("Total differences {0}".format(counter))
