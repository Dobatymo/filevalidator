from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from os import fspath
from pathlib import Path
from typing import Dict, Optional, Sequence

from genutility.datetime import now
from genutility.filesystem import MyDirEntry, entrysuffix, scandir_rec
from genutility.json import read_json

import plugins
from plug import Filetypes, Plugin
from xmlreport import XmlReport, load_report

logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = Path("./reports")
DEFAULT_STYLE_SHEET = "report.xsl"

def validate_paths(paths, report_dir, xslfile, resumefile=None, recursive=False, relative=False, ignore=None):
	# type: (Sequence[str], Path, str, Optional[str], bool, bool, Optional[set]) -> None

	for name in plugins.__all__:
		__import__("plugins." + name)

	for class_, extensions in Filetypes.PLUGINS.items():
		logger.info("Loaded Filetype plugin %s for: %s", class_.__name__, ", ".join(extensions))

	if resumefile:
		resume_info = load_report(resumefile)
	else:
		resume_info = {}

	validators = {}  # type: Dict[str, Plugin]
	no_validators = ignore or set()

	filename = "report_{}.xml".format(now().isoformat("_").replace(":", "."))
	with XmlReport(fspath(report_dir / filename), xslfile) as report:

		for dir in paths:
			for entry in scandir_rec(dir, dirs=False, rec=recursive, follow_symlinks=False, relative=relative):

				logger.debug("Processing %s", fspath(entry))
				ext = entrysuffix(entry).lower()[1:]

				if relative:
					assert isinstance(entry, MyDirEntry)
					outpath = entry.relpath
				else:
					outpath = fspath(entry)

				if ext in no_validators:
					continue

				# check if resume info available

				try:
					code, message = resume_info[outpath]
				except KeyError:
					pass
				else:
					logger.debug("Copied information for %s", outpath)
					report.write(outpath, str(code), message)
					continue

				# get validator for ext

				validator = None
				try:
					validator = validators[ext]
				except KeyError:
					for class_, extensions in Filetypes.PLUGINS.items():
						if ext in extensions:
							try:
								config = read_json("config/{}.json".format(class_.__name__))
							except FileNotFoundError:
								logger.info("Could not find config for '%s'", class_.__name__)
								config = {}
							except ValueError:
								logger.exception("Could not load config for '%s'", class_.__name__)
								config = {}
							try:
								validator = validators[ext] = class_(**config)
							except TypeError:
								logger.error("Cannot use '%s' without config", class_.__name__)
				if not validator:
					no_validators.add(ext)
					logger.info("No validator found for file extension '%s'", ext)
					continue

				# validate file

				try:
					code, message = validator.validate(fspath(entry), ext)
				except KeyboardInterrupt:
					logger.warning("Validating '%s' interrupted", fspath(entry))
					raise
				except Exception:
					logger.exception("Validating '%s' failed", fspath(entry))
				else:
					report.write(outpath, str(code), message)

#from gooey import Gooey
#@Gooey
def main():

	from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

	from genutility.args import is_dir, is_file, lowercase, out_dir

	parser = ArgumentParser(description="FileValidator", formatter_class=ArgumentDefaultsHelpFormatter)
	parser.add_argument("-d", "--reportdir", type=out_dir, default=DEFAULT_REPORTS_DIR, help="set output directory for reports")
	parser.add_argument("-x", "--xsl", dest="xslfile", default=DEFAULT_STYLE_SHEET, help="set XSL style sheet file")
	parser.add_argument("-r", "--recursive", action="store_true", help="scan directories recursively")
	parser.add_argument("-v", "--verbose", action="store_true", help="output debug info")
	parser.add_argument("-i", "--ignore", metavar="EXT", nargs='+', type=lowercase, default=[], help="extensions to ignore")
	parser.add_argument("--relative", action="store_true", help="Output relative paths")
	parser.add_argument("--resume", type=is_file, help="Resume validation using a previous XML report")
	parser.add_argument("paths", metavar="DIRECTORY", nargs='+', type=is_dir, help="directories to create report for")
	args = parser.parse_args()

	if args.verbose:
		logging.basicConfig(level=logging.DEBUG)
	else:
		logging.basicConfig(level=logging.INFO)

	validate_paths(args.paths, args.reportdir, args.xslfile, args.resume, args.recursive, args.relative, args.verbose, set(args.ignore))

if __name__ == "__main__":
	main()
