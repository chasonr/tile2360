# tile2360
NetHack tileset converter for version 3.6.0

Here is a Python program that will take a NetHack 3.4.3 tileset in BMP format and convert it to a form usable with 3.6.0.

If you have a Mac or Linux, you probably already have Python (or can install it with your package manager). Windows users can run this with ActiveState Python.

Use ./tile2360.py -h for a complete list of options. Most tilesets convert without needing any options; the program assumes that the image contains 40 tiles per row and that tiles are square, unless the tile size is given. The output file name just adds "-360" before the ".bmp" suffix, unless the command line specifies a different name.

New tiles are created as follows:

* Monster tiles are converted to grayscale to form statue tiles. To give better results with tilesets that do not use black backgrounds, the tile is compared to the floor tile; a pixel that is different from the floor is converted.

* The number of scroll appearances increases from 25 to 41; tile2360.py repeats the first 16 scroll tiles to make 41.

* The tile for the darkened portion of a floor is created by halving the luminance of the existing floor tile.

* Eight other tiles are filled in with a placeholder, which appears as a solid red tile with a black X through it. This is for use by tileset authors, who can then fill in the missing tiles. The missing tiles are, in order:

  * glob of gray ooze, brown pudding, green slime and black pudding, in that order; this is a block of four missing tiles appearing after the meat ring

  * novel -- this is a single missing tile appearing after all the spellbooks except the Book of the Dead

  * The vibrating square -- this is a single missing tile appearing after all the traps

  * Poison cloud and valid position -- these are two missing tiles appearing after the sparkles
