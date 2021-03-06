from __future__ import generator_stop

import wave
from typing import Tuple

from genutility.iter import consume

from plug import Filetypes


def iter_wave(wr, chunksize=10000):
	frames = wr.getnframes()
	while frames > 0:
		n = min(frames, chunksize)
		yield wr.readframes(n)
		frames -= chunksize

@Filetypes.plugin(["wav"])
class WAVE(object):

	def __init__(self):
		pass

	def validate(self, path, ext):
		# type: (str, str) -> Tuple[int, str]

		try:
			with wave.open(path, "rb") as wr:
				consume(iter_wave(wr))

			return (0, "")
		except wave.Error as e:
			return (1, str(e))
		except Exception as e:
			return (1, str(e))
