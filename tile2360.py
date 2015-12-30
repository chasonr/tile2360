#!/usr/bin/env python
# tile2360.py -- convert NetHack 3.4.3 tile sets most of the way to 3.6.0
#
# Copyright (c) 2015, Ray Chason
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import argparse
import os.path
import struct
import sys

# A Bitmap image, with some extra methods for tile mapping
class Bitmap(object):
    def __init__(self, inpname):
        # TODO: This assumes the BITMAPINFOHEADER structure. Add support for
        # other bitmap formats.

        # Read the header
        fp = open(inpname, "rb")
        header = fp.read(54)

        (magic,
        self.bmp_size,
        reserved,
        self.image_offset,
        self.header_size,
        self.width,
        self.height,
        self.num_planes,
        self.bits_per_pixel,
        self.compression,
        self.image_size,
        self.horiz_res,
        self.vert_res,
        self.num_colors,
        self.num_important_colors) = struct.unpack("<2s6L2H6L", header)

        # Check various header fields for unsupported stuff
        if magic != "BM":
            raise RuntimeError, "%s is not in .BMP format" % inpname

        if self.header_size != 40:
            raise RuntimeError, "%s has an unsupported header type (%d)" % \
                    (inpname, self.header_size)

        if self.num_planes != 1:
            raise RuntimeError, "%s has %d planes, not supported" % \
                    (inpname, self.num_planes)

        if self.compression != 0:
            raise RuntimeError, "%s is compressed (%d), and not supported" % \
                    (inpname, self.compression)

        if self.bits_per_pixel not in (1, 2, 4, 8, 24, 32):
            raise RuntimeError, "%s has %d bits per pixel, not supported" % \
                    (inpname, self.bits_per_pixel)

        # Read the palette
        if self.bits_per_pixel <= 8:
            if self.num_colors == 0:
                self.num_colors = 1 << self.bits_per_pixel
            self.palette = [ None ] * self.num_colors
            for i in xrange(0, self.num_colors):
                b, g, r, z = struct.unpack("<4B", fp.read(4))
                self.palette[i] = (b, g, r)
        else:
            self.palette = None

        # Read the pixels
        fp.seek(self.image_offset)
        self.image = [ None ] * self.height
        row_size = ((self.bits_per_pixel * self.width + 31) / 32) * 4
        if self.bits_per_pixel <= 8:
            # Palettized image; convert to 24 bit
            pixels_per_byte = 8 / self.bits_per_pixel
            mask = (1 << self.bits_per_pixel) - 1
            for y in xrange(0, self.height):
                row_bytes = fp.read(row_size)
                row_bytes = map(
                        lambda x : struct.unpack('<1B', x)[0],
                        row_bytes)
                row = [ None ] * self.width
                self.image[self.height - 1 - y] = row
                shift = 8
                for x in xrange(0, self.width):
                    if shift <= 0:
                        shift = 8
                    shift -= self.bits_per_pixel
                    x_hi = x / pixels_per_byte
                    i = (row_bytes[x_hi] >> shift) & mask
                    row[x] = self.palette[i]
        else:
            # 24 or 32 bits per pixel
            bytes_per_pixel = self.bits_per_pixel / 8
            for y in xrange(0, self.height):
                row_bytes = fp.read(row_size)
                row_bytes = map(
                        lambda x : struct.unpack('<1B', x)[0],
                        row_bytes)
                row = [ None ] * self.width
                self.image[self.height - 1 - y] = row
                for x in xrange(0, self.width):
                    x2 = x * bytes_per_pixel
                    row[x] = tuple(row_bytes[x2 : x2 + 3])
        self.bits_per_pixel = 24

        # These are yet unknown
        self.tile_width = None
        self.tile_height = None
        self.tiles_per_row = None
        self.tile_rows = None
        self.tiles = None

    # Split the image into tiles
    def split(self, tile_width, tile_height):
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.tiles_per_row = self.width / tile_width
        self.tile_rows = self.height / tile_height
        num_tiles = self.tiles_per_row * self.tile_rows
        self.tiles = [ None ] * num_tiles

        for t in xrange(0, num_tiles):
            tile = [ None ] * tile_height
            self.tiles[t] = tile
            t_col = t % self.tiles_per_row
            t_row = t / self.tiles_per_row
            t_x = t_col * tile_width
            t_y = t_row * tile_height
            for y in xrange(0, tile_height):
                tile[y] = self.image[t_y + y][t_x : t_x + tile_width]

    # Rearrange the tiles to match the NetHack 3.6.0 order
    def remap(self, no_statues):
        # If tile_map[X] = Y, the tile in position X for 3.6.0 comes from
        # position Y for 3.4.3. Negative numbers indicate tiles that cannot
        # be directly mapped.
        tile_map = [
            # Monsters
               0,    1,    2,    3,    4,    5,    6,    7,    8,    9,
              10,   11,   12,   13,   14,   15,   16,
            # dingo (19) placed before dog (17)
              19,   17,   18,
              20,   21,
            # winter wolf cub (23) placed before warg (22)
              23,   22,
              24,   25,   26,   27,   28,   29,
              30,   31,   32,   33,   34,   35,   36,   37,   38,   39,
              40,   41,   42,   43,   44,   45,   46,   47,   48,   49,
              50,   51,   52,   53,   54,   55,   56,   57,   58,   59,
              60,   61,   62,   63,   64,   65,   66,   67,   68,   69,
              70,   71,   72,   73,   74,   75,   76,   77,   78,   79,
              80,   81,   82,   83,   84,   85,   86,   87,   88,   89,
              90,   91,   92,   93,   94,   95,   96,   97,   98,   99,
             100,
            # pony (104) placed before white unicorn (101)
             104,  101,  102,  103,
             105,  106,  107,  108,  109,
             110,  111,  112,  113,  114,  115,  116,  117,  118,  119,
             120,  121,  122,  123,  124,  125,  126,  127,  128,  129,
             130,  131,  132,  133,  134,  135,  136,  137,  138,  139,
             140,  141,  142,  143,  144,  145,  146,  147,  148,  149,
             150,  151,  152,  153,  154,  155,  156,  157,  158,  159,
             160,  161,  162,  163,  164,  165,  166,  167,  168,  169,
             170,  171,  172,  173,  174,
            # ettin (176) placed before storm giant (175)
             176,  175,
             177,  178,  179,
             180,  181,  182,  183,  184,  185,  186,  187,  188,  189,
             190,  191,  192,  193,  194,  195,  196,  197,  198,  199,
             200,  201,  202,  203,  204,  205,  206,  207,  208,  209,
            # green slime (211) placed before black pudding (210)
             211,  210,
             212,  213,  214,  215,  216,  217,
            # python (219) placed before pit viper (218)
             219,  218,
             220,  221,  222,  223,  224,  225,  226,  227,  228,  229,
             230,  231,  232,  233,  234,  235,  236,  237,  238,  239,
             240,  241,  242,  243,  244,  245,  246,  247,
            # ghoul (249) placed before giant zombie (248)
             249,  248,
             250,  251,  252,  253,  254,  255,  256,  257,  258,  259,
             260,  261,  262,  263,  264,  265,  266,  267,  268,  269,
             270,  271,  272,
            # nurse (273) placed after sergeant (281)
             274,  275,  276,  277,  278,  279,  280,  281,  273,
             282,  283,  284,  285,  286,  287,  288,  289,
             290,  291,  292,
            # succubus (294) placed before horned devil (293)
             294,  293,
             295,  296,  297,  298,  299,
             300,  301,  302,  303,  304,
            # sandestin (319) placed before balrog (305)
             319,  305,  306,  307,  308,  309,  310,  311,  312,  313,
             314,  315,  316,  317,  318,
             320,  321,  322,  323,  324,  325,  326,  327,  328,  329,
             330,  331,  332,  333,  334,  335,  336,  337,  338,  339,
             340,  341,  342,  343,  344,  345,  346,  347,  348,  349,
             350,  351,  352,  353,  354,  355,  356,  357,  358,  359,
             360,  361,  362,  363,  364,  365,  366,  367,  368,  369,
             370,  371,  372,  373,  374,  375,  376,  377,  378,  379,
             380,  381,  382,  383,  384,  385,  386,  387,  388,  389,
             390,  391,  392,  393,

            # Objects:
                                     394,  395,  396,  397,  398,  399,
             400,  401,  402,  403,  404,  405,  406,  407,  408,  409,
             410,  411,  412,  413,  414,  415,  416,  417,  418,  419,
             420,  421,  422,  423,  424,  425,  426,  427,  428,  429,
             430,  431,  432,  433,  434,  435,  436,  437,  438,  439,
             440,  441,  442,  443,  444,  445,  446,  447,  448,  449,
             450,  451,  452,  453,  454,  455,  456,  457,  458,  459,
             460,  461,  462,  463,  464,  465,  466,  467,  468,  469,
             470,  471,  472,  473,  474,  475,  476,  477,  478,  479,
             480,  481,  482,  483,  484,  485,  486,  487,  488,  489,
             490,  491,  492,  493,  494,  495,  496,  497,  498,  499,
             500,  501,  502,  503,  504,  505,  506,  507,  508,  509,
             510,  511,  512,  513,  514,  515,  516,  517,  518,  519,
             520,  521,  522,  523,  524,  525,  526,  527,  528,  529,
             530,  531,  532,  533,  534,  535,  536,  537,  538,  539,
             540,  541,  542,  543,  544,  545,  546,  547,  548,  549,
             550,  551,  552,  553,  554,  555,  556,  557,  558,  559,
             560,  561,  562,  563,  564,  565,  566,  567,  568,  569,
             570,  571,  572,  573,  574,  575,  576,  577,  578,  579,
             580,  581,  582,  583,  584,  585,  586,  587,  588,  589,
             590,  591,  592,  593,  594,  595,  596,  597,  598,  599,
             600,  601,  602,  603,  604,  605,  606,  607,  608,  609,
             610,  611,  612,  613,  614,  615,  616,  617,  618,  619,
             620,  621,  622,  623,  624,  625,  626,  627,  628,  629,
             630,  631,  632,  633,  634,  635,  636,  637,  638,  639,
             640,  641,
              -1, # glob of gray ooze
              -1, # glob of brown pudding
              -1, # glob of green slime
              -1, # glob of black pudding
             642,  643,  644,  645,  646,  647,  648,  649,
             650,  651,  652,  653,  654,  655,  656,  657,  658,  659,
             660,  661,  662,  663,  664,  665,  666,  667,  668,  669,
             670,  671,  672,  673,  674,  675,  676,  677,  678,  679,
             680,  681,  682,  683,  684,  685,  686,  687,  688,  689,
            # Random scroll appearances begin here
             690,  691,  692,  693,  694,  695,  696,  697,  698,  699,
             700,  701,  702,  703,  704,  705,  706,  707,  708,  709,
             710,  711,  712,  713,  714,
            # New random scroll appearances. Repeat the first 16 above
             690,  691,  692,  693,  694,  695,  696,  697,  698,  699,
             700,  701,  702,  703,  704,  705,
            # Random scroll appearances end here
             715,  716,  717,  718,  719,
             720,  721,  722,  723,  724,  725,  726,  727,  728,  729,
             730,  731,  732,  733,  734,  735,  736,  737,  738,  739,
             740,  741,  742,  743,  744,  745,  746,  747,  748,  749,
             750,  751,  752,  753,  754,  755,  756,  757,
              -1, # Novel
             758,  759,
             760,  761,  762,  763,  764,  765,  766,  767,  768,  769,
             770,  771,  772,  773,  774,  775,  776,  777,  778,  779,
             780,  781,  782,  783,  784,  785,  786,  787,  788,  789,
             790,  791,  792,  793,  794,  795,  796,  797,  798,  799,
             800,  801,  802,  803,  804,  805,  806,  807,  808,  809,
             810,  811,  812,  813,  814,  815,  816,  817,  818,  819,
             820,  821,  822,  823,  824,  825,  826,  827,  828,

            # Dungeon features, missiles, explosions, etc.
             829,
             830,  831,  832,  833,  834,  835,  836,  837,  838,  839,
             840,  841,  842,  843,  844,  845,  846,  847,  848,
              -2, # darkened part of a room
             849,
             850,  851,  852,  853,  854,  855,  856,  857,  858,  859,
             860,  861,  862,  863,  864,  865,  866,  867,  868,  869,
             870,  871,  872,  873,  874,  875,  876,  877,  878,  879,
             880,  881,  882,  883,  884,  885,  886,  887,  888,  889,
             890,  891,
              -1, # vibrating square
             892,  893,  894,  895,  896,  897,  898,  899,
             900,  901,  902,  903,
              -1, # poison cloud
              -1, # valid position
             904,  905,  906,  907,  908,  909,
             910,  911,  912,  913,  914,  915,  916,  917,  918,  919,
             920,  921,  922,  923,  924,  925,  926,  927,  928,  929,
             930,  931,  932,  933,  934,  935,  936,  937,  938,  939,
             940,  941,  942,  943,  944,  945,  946,  947,  948,  949,
             950,  951,  952,  953,  954,  955,  956,  957,  958,  959,
             960,  961,  962,  963,  964,  965,  966,  967,  968,  969,
             970,  971,  972,  973,  974,  975,  976,  977,  978,  979,
             980,  981,  982,  983,  984,  985,  986,  987,  988,  989,
             990,  991,  992,  993,  994,  995,  996,  997,  998,  999,
            1000, 1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009,
            1010, 1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019,
            1020, 1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028, 1029,
            1030, 1031, 1032, 1033, 1034, 1035, 1036, 1037, 1038, 1039,
            1040, 1041, 1042, 1043, 1044, 1045, 1046, 1047, 1048, 1049,
            1050, 1051, 1052, 1053, 1054, 1055, 1056
            # then repeat the monster glyphs to make statues
        ]

        # Map monsters, objects and dungeon features
        map_size = len(tile_map)
        new_tiles = [ None ] * (map_size + 394)
        for i in xrange(0, map_size):
            m = tile_map[i]
            if m >= 0:
                new_tiles[i] = self.tiles[m]
            elif m == -2:
                new_tiles[i] = self.darkenedTile(self.tiles[m - 1])
            else:
                new_tiles[i] = self.placeHolderTile()

        # Generate statue tiles
        if no_statues:
            for i in xrange(0, 394):
                new_tiles[i + map_size] = self.tiles[824] # statue
        else:
            for i in xrange(0, 394):
                new_tiles[i + map_size] = self.makeStatue(
                        new_tiles[i], self.tiles[848])

        # Update the number of tile rows
        self.tile_rows = (len(new_tiles) + self.tiles_per_row - 1) \
                / self.tiles_per_row

        # Add some blank tiles to fill out the last row
        num_tiles = self.tile_rows * self.tiles_per_row
        if len(new_tiles) < num_tiles:
            blank_tile = self.blankTile()
            while len(new_tiles) < num_tiles:
                new_tiles.append(blank_tile)
        self.tiles = new_tiles

    # Rejoin the tiles into a new image
    def join(self):
        # New image dimensions; normally width will be unchanged
        self.width = self.tiles_per_row * self.tile_width
        self.height = self.tile_rows * self.tile_height

        # Create blank image
        self.image = [ None ] * self.height
        for i in xrange(0, self.height):
            self.image[i] = []

        # Add each tile to the end of its row
        for i in xrange(0, len(self.tiles)):
            t_row = i / self.tiles_per_row
            t_y = t_row * self.tile_height
            tile = self.tiles[i]
            for j in xrange(0, self.tile_height):
                self.image[t_y + j].extend(tile[j])

    # Write the image to the output file
    def write(self, outname):
        fp = open(outname, "wb")

        # Write a palettized image if possible without degradation
        self.buildPalette()
        palette_map = {}
        if self.bits_per_pixel <= 8:
            for i in xrange(0, len(self.palette)):
                palette_map[self.palette[i]] = i

        # Write the header, with placeholders for some fields
        self.writeHeader(fp)

        # Write the palette if any
        if self.bits_per_pixel <= 8:
            for i in xrange(0, self.num_colors):
                fp.write(struct.pack("<4B",
                        self.palette[i][0],
                        self.palette[i][1],
                        self.palette[i][2],
                        0))
        self.image_offset = fp.tell()

        # Write the pixels
        row_size = ((self.bits_per_pixel * self.width + 31) / 32) * 4
        if self.bits_per_pixel <= 8:
            for y in xrange(0, self.height):
                row = self.image[self.height - 1 - y]
                bits = 0
                byte = 0
                count = 0
                for x in xrange(0, self.width):
                    index = palette_map[row[x]]
                    byte = (byte << self.bits_per_pixel) | index
                    bits += self.bits_per_pixel
                    if bits >= 8:
                        fp.write(struct.pack("<1B", byte))
                        byte = 0
                        bits = 0
                        count += 1
                if bits != 0:
                    byte <<= 8 - bits
                    fp.write(struct.pack("<1B", byte))
                    count += 1
                while count < row_size:
                    fp.write(struct.pack("<1B", 0))
                    count += 1
        else:
            for y in xrange(0, self.height):
                row = self.image[self.height - 1 - y]
                for x in xrange(0, self.width):
                    for byte in row[x]:
                        fp.write(struct.pack("<1B", byte))
                count = len(row) * len(row[0])
                while count < row_size:
                    fp.write(struct.pack("<1B", 0))
                    count += 1

        # Write the header with the correct offsets
        self.bmp_size = fp.tell()
        fp.seek(0)
        self.writeHeader(fp)

    # Given the existing image, build a palette if possible
    # If there are more than 256 unique colors, build no palette; we will
    # write a 24 bit bitmap
    def buildPalette(self):
        # Collect all colors present in the image
        color_count = {}
        for row in self.image:
            for pixel in row:
                if pixel not in color_count:
                    color_count[pixel] = 0
                color_count[pixel] += 1

        # Get the list of unique colors; this will be the palette
        palette = color_count.keys()
        self.num_colors = len(palette)
        if self.num_colors > 256:
            # We will write a 24 bit bitmap
            self.bits_per_pixel = 24
            self.palette = None
            return

        # Arrange in descending order of occurrence
        palette.sort(lambda a, b : color_count[b] - color_count[a])

        # Set a valid bit-per-pixel count, with the fewest bits that will
        # encompass the palette
        self.palette = palette
        if self.num_colors < 2:
            self.bits_per_pixel = 1
        elif self.num_colors < 4:
            self.bits_per_pixel = 2
        elif self.num_colors < 16:
            self.bits_per_pixel = 4
        else:
            self.bits_per_pixel = 8

    # A black tile, to fill the last row
    def blankTile(self):
        return [ [ (0, 0, 0) ] * self.tile_width ] * self.tile_height

    # A placeholder tile, for the tiles that cannot otherwise be derived
    # This will appear as a red block with a black X through it
    def placeHolderTile(self):
        red   = ( 0x00, 0x00, 0xFF )
        black = ( 0x00, 0x00, 0x00 )
        tile = [ None ] * self.tile_height
        for y in xrange(0, self.tile_height):
            tile[y] = [ red ] * self.tile_width
        m = min(self.tile_width, self.tile_height)
        for x in xrange(0, m):
            tile[x][x] = black
            tile[x][m - 1 - x] = black
        return tile

    # A tile at half brightness to the input
    def darkenedTile(self, inptile):
        outtile = [ None ] * len(inptile)
        for y in xrange(0, len(outtile)):
            inprow = inptile[y]
            outrow = [ None ] * len(inprow)
            outtile[y] = outrow
            for x in xrange(0, len(inprow)):
                inp = inprow[x]
                out = ( inp[0] >> 1, inp[1] >> 1, inp[2] >> 1 )
                outrow[x] = out
        return outtile

    # A statue tile.
    # To assist in transforming tile sets that do not use a black background,
    # this accepts the floor tile. A pixel that is different from the floor
    # tile is considered to be foreground, and converted to grayscale.
    def makeStatue(self, inptile, floor):
        outtile = [ None ] * len(inptile)
        for y in xrange(0, len(outtile)):
            inprow = inptile[y]
            floor_row = floor[y]
            outrow = [ None ] * len(inprow)
            outtile[y] = outrow
            for x in xrange(0, len(inprow)):
                inp = inprow[x]
                fl = floor_row[x]
                if inp == fl:
                    # background
                    out = inp
                else:
                    # foreground
                    gray = (inp[0] + inp[1] + inp[2]) / 3
                    out = ( gray, gray, gray )
                outrow[x] = out
        return outtile

    # Write a BITMAPINFOHEADER-type header for a BMP file
    def writeHeader(self, fp):
        fp.write(struct.pack("<2s6L2H6L",
                "BM",
                self.bmp_size,
                0,
                self.image_offset,
                self.header_size,
                self.width,
                self.height,
                self.num_planes,
                self.bits_per_pixel,
                self.compression,
                self.image_size,
                self.horiz_res,
                self.vert_res,
                self.num_colors,
                self.num_important_colors))

# Convert one bitmap file
# inpname is the name of the file to be converted; args contains the arguments
# as parsed by the ArgumentParser object
def convertBitmap(inpname, args):
    # Collect arguments from args
    tile_width = args.tile_width
    tile_height = args.tile_height
    no_statues = args.no_statues
    outname = args.output

    # Provide default output file name
    if outname is None:
        d, n = os.path.split(inpname)
        dot = n.rfind('.')
        if dot != -1:
            n = n[:dot]
        n += '-360.bmp'
        outname = os.path.join(d, n)

    # Read the bitmap image
    bmp = Bitmap(inpname)

    # Provide default tile dimensions
    if tile_width is None:
        tile_width = bmp.width / 40
    if tile_height is None:
        tile_height = tile_width

    # Split the bitmap into tiles
    bmp.split(tile_width, tile_height)

    # Remap into 3.6.0 arrangement
    bmp.remap(no_statues)

    # Rejoin into a single image
    bmp.join()

    # Write to disk
    bmp.write(outname)

# Define command line arguments for this program
parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description='Convert NetHack 3.4.3 tile sets for use with 3.6.0',
            epilog='''
If --tile-width is not specified, it is the image width divided by 40.
If --tile-height is not specified, it is equal to the tile width.
If --no-statues is specified, statue glyphs are copied from the 3.4.3 statue
   glyph; if not, statue glyphs are generated by converting the monster glyphs
   to grayscale.

Images must be in BMP format.

If --output is not specified, the output file name is <input-name>-360.bmp.
Multiple images can be converted, but only if --output is not specified.
''')
parser.add_argument('images', metavar='image', type=str, nargs='+',
            help='Name of a tile set image for NetHack 3.4.3')
parser.add_argument('--tile-width', '-x', dest='tile_width', type=int,
            help='Width of a single tile in pixels')
parser.add_argument('--tile-height', '-y', dest='tile_height', type=int,
            help='Height of a single tile in pixels')
parser.add_argument('--no-statues', '-s', dest='no_statues',
            action='store_true',
            help='Do not derive statues from monsters')
parser.add_argument('--output', '-o', dest='output', type=str,
            help='Name of output image')

args = parser.parse_args()
if len(args.images) > 1 and args.output is not None:
    sys.stderr.write("Cannot specify --output with more than one image name\n")
    sys.exit(1)

# Process each image in turn
rc = 0
for image in args.images:
    if not convertBitmap(image, args):
        rc = 1
sys.exit(rc)
