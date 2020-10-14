from __future__ import absolute_import, division, print_function, unicode_literals

from future.utils import viewitems

import logging
from datetime import datetime

from genutility.compat import FileNotFoundError
from genutility.compat.os import fspath
from genutility.compat.pathlib import Path
from genutility.filesystem import entrysuffix, scandir_rec
from genutility.json import read_json
from genutility.twothree.filesystem import sbs

import plugins
from plug import Filetypes
from xmlreport import XmlReport, load_report

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

DEFAULT_REPORTS_DIR = Path("./reports")
DEFAULT_STYLE_SHEET = "report.xsl"

def validate_paths(paths, report_dir, xslfile, resumefile=None, recursive=False, relative=False, verbose=False, ignore=None):
	# type: (Sequence[str], str, str, Optional[str], bool, bool, Optional[set]) -> None

	if verbose:
		logging.basicConfig(level=logging.DEBUG)
	else:
		logging.basicConfig(level=logging.INFO)

	logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

	for name in plugins.__all__:
		__import__("plugins." + name)

	for class_, extensions in viewitems(Filetypes.PLUGINS):
		logger.info("Loaded Filetype plugin %s for: %s", class_.__name__, ", ".join(extensions))

	if resumefile:
		resume_info = load_report(resumefile)
	else:
		resume_info = {}

	validators = {}
	no_validators = ignore or set()

	filename = "report_{}.xml".format(datetime.now().isoformat(sbs("_")).replace(":", "."))
	with XmlReport(report_dir / filename, xslfile) as report:

		for dir in paths:
			for entry in scandir_rec(dir, dirs=False, rec=recursive, follow_symlinks=False, relative=relative):

				logger.debug("Processing %s", fspath(entry))
				ext = entrysuffix(entry).lower()[1:]

				if relative:
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
					for class_, extensions in viewitems(Filetypes.PLUGINS):
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
				except Exception as e:
					logger.exception("Validating '%s' failed", fspath(entry))
				else:
					report.write(outpath, str(code), message)

from gooey import Gooey


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

	validate_paths(args.paths, args.reportdir, args.xslfile, args.resume, args.recursive, args.relative, args.verbose, set(args.ignore))

if __name__ == "__main__":
	main()
