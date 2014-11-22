from __future__ import unicode_literals, absolute_import

import os, os.path, logging
from datetime import datetime

from plug import Filetypes
from xmlreport import xmlreport
import plugins

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def scandir(top, rec, followlinks=False):
    def joiner(dir, dirlist):
        for d in dirlist:
            yield os.path.join(dir, d)

    walker = os.walk(top, followlinks=followlinks)
    
    dirpath, __, filenames = next(walker)
    for path in joiner(dirpath, filenames):
        yield path
    if not rec:
        return
    for dirpath, __, filenames in walker:
        for path in joiner(dirpath, filenames):
            yield path

def main(DIRS, report_dir, xslfile, recursive):

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s\t%(name)s\t%(funcName)s\t%(message)s")

    for name in plugins.__all__:
        __import__("plugins." + name)

    for class_, extensions in Filetypes.PLUGINS.iteritems():
        logger.info("Loaded Filetype plugin {} for: {}".format(class_.__name__, ", ".join(extensions)))

    validators = {}
    no_validators = set()

    report = xmlreport(os.path.join(report_dir, "report_{}.xml".format(datetime.now().isoformat(b"_")).replace(":", ".")), xslfile)

    for dir in DIRS:
        for path in scandir(dir, rec=recursive):
            print(path)
            ext = os.path.splitext(path)[1][1:].lower()
            
            if ext in no_validators:
                continue

            validator = None
            try:
                validator = validators[ext]
            except KeyError:
                for class_, extensions in Filetypes.PLUGINS.iteritems():
                    if ext in extensions:
                        validators[ext] = validator = class_()
            if not validator:
                no_validators.add(ext)
                logging.debug("No validator found for file extension '{}'".format(ext))
                continue
            try:
                code, message = validator.validate(os.path.abspath(path), ext)
                report.write(path, str(code), message)
                report.newline()
            except Exception as e:
                logger.exception("Validating '{}' failed".format(path))

    report.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description = "pyFileValidator")
    #parser.add_argument("-d", "--reportdir", dest="reportdir", default=os.path.join(os.getenv("APPDATA"), "pyFileValidator"), help="set output directory for reports")
    parser.add_argument("-d", "--reportdir", dest="reportdir", default="reports", help="set output directory for reports")
    parser.add_argument("-x", "--xsl", dest="xslfile", default="report.xsl", help="set xsl style sheet file")
    parser.add_argument("-r", "--recursive", dest="recursive", type=bool, default=True, help="scan directories recursively")
    parser.add_argument("DIRECTORY", nargs='+', help="directories to create report for")
    args = parser.parse_args()

    print(args)

    if not os.path.isdir(args.reportdir):
        try:
            os.mkdir(args.reportdir)
        except EnvironmentException:
            exit("Error: '{}' is not a valid directory.".format(args.reportdir))

    main(args.DIRECTORY, args.reportdir, args.xslfile, args.recursive)