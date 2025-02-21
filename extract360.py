"""Program to extract typical XBox 360 files.
   It can handle LIVE/PIRS, CON (partially), FMIM, and XUIZ files.

   What about CRA (aka .arc) files?  (Dead Rising demo)

   Copyright (c) 2007, 2008, Rene Ladan <r.c.ladan@gmail.com>, 2-claused BSD
   license. Portions from various contributors as mentioned in-source.

   Note that it dumps UTF-16 characters in text strings as-is.
"""

################################################################################

def check_size(fsize, minsize):
    """Ensure that the filesize is at least minsize bytes.

       @param fsize the filesize
       @param minsize the minimal file size
       @return fsize >= minsize
    """

    if fsize < minsize:
        print("Input file too small: %i instead of at least %i bytes." % \
            (fsize, minsize))
    return fsize >= minsize

################################################################################

def nice_open_file(filename):
    """Checks if the output file with the given name already exists,
       and if so, asks for overwrite permission.

       @param filename name of the output file to open
       @return overwrite permission
    """

    if os.path.isfile(filename):
        print(filename, "already exists, overwrite? (y/n)", )
        answer = input("")
        return len(answer) > 0 and answer[0] in ["Y", "y"]
    else:
        return True

################################################################################

def nice_open_dir(dirname):
    """Checks if the output directory with the given name already exists,
       and if so, asks for overwrite permission.  This means that any file
       in that directory might be overwritten.

       @param dirname name of the output directory to open
       @return overwrite permission
    """

    if os.path.isdir(dirname):
        print(dirname, "already exists, ok to overwrite files in it? (y/n)", )
        answer = input("")
        return len(answer) > 0 and answer[0] in ["Y", "y"]
    else:
        return True

################################################################################

def do_mkdir(dirname):
    """Version of os.mkdir() which does not throw an exception if the directory
       already exists.

       @param dirname name of the directory to create
    """

    try:
        os.mkdir(dirname)
    except OSError as xxx_todo_changeme:
        (errno) = xxx_todo_changeme
        if errno == 17:
            pass # directory already exists

################################################################################

def rm_nul(instring):
    """Remove embedded NUL characters from the input string.

       @param instring the input string
       @return stripped version of instring
    """

    rstr = ""
    for i in instring:
        if ord(i) > 0:
            rstr += i
    return rstr

################################################################################

def strip_blanks(instring):
    """Strip the leading and trailing blanks from the input string.
       Blanks are: 0x00 (only trailing) space \t \n \r \v \f 0xFF

       @param instring the input string
       @return stripped version of instring
    """
    rstr = instring.rstrip("\0 \t\n\r\v\f\377")
    return rstr.lstrip(" \t\n\r\v\f\377")

################################################################################

def open_info_file(infile):
    """Open the informational text file.
       The name is based on that of the input file.

       @param infile pointer to the input file
       @return pointer to the informational text file or None if there was no
               overwrite permission
    """

    txtname = os.path.basename(infile.name) + ".txt"
    if nice_open_file(txtname):
        print("Writing information file", txtname)
        txtfile = open(txtname, "w")
        return txtfile
    else:
        return None

################################################################################

def dump_png(infile, pnglen, maxlen, pngid):
    """Dump the embedded PNG file from the archive file to an output file.

       @param infile pointer to the archive file
       @param pnglen size of the PNG file in bytes
       @param maxlen maximum size of the PNG file in bytes
       @param pngid indicates if this is the first or second PNG file.
    """

    # dump PNG icon
    if pnglen <= maxlen:
        outname = os.path.basename(infile.name) + "_" + pngid + ".png"
        if nice_open_file(outname):
            buf = infile.read(pnglen)
            print("Writing PNG file", outname)
            outfile = open(outname, "wb")
            outfile.write(buf)
            outfile.close()
    else:
        print("PNG image %s too large (%i instead of maximal %i bytes), " \
            "file not written." % (pngid, pnglen, maxlen))

################################################################################

def dump_info(infile, txtfile, what):
    """Dumps the 9 information strings from the input file.

       @param infile pointer to the input file
       @param txtfile pointer to the resulting text file
       @param what indicates if the information consists of titles or
              descriptions
    """

    txtfile.write("\n" + what + ":")
    for i in range(9):
        info = strip_blanks(infile.read(0x100).decode("utf-8"))
        if len(info) > 0:
            txtfile.write(lang[i] + ":" + info)

################################################################################

def mstime(intime):
    """Convert the time given in Microsoft format to a normal time tuple.

       @param intime the time in Microsoft format
       @return the time tuple
    """

    num_d = (intime & 0xFFFF0000) >> 16
    num_t = intime & 0x0000FFFF
    # format below is : year, month, day, hour, minute, second,
    #                   weekday (Monday), yearday (unused), DST flag (guess)
    return ((num_d >> 9) + 1980, (num_d >> 5) & 0x0F, num_d & 0x1F,
            (num_t & 0xFFFF) >> 11, (num_t >> 5) & 0x3F, (num_t & 0x1F) * 2,
            0, 0, -1)

################################################################################

def do_utime(targetname, atime, mtime):
    """Set the access and update date/time of the target.
       Taken from tarfile.py (builtin lib)

       @param targetname name of the target
       @param atime the desired access date/time
       @param mtime the desired update date/time
    """

    if not hasattr(os, "utime"):
        return
    if not (sys.platform == "win32" and os.path.isdir(targetname)):
        # Using utime() on directories is not allowed on Win32 according to
        # msdn.microsoft.com
        os.utime(targetname,
            (time.mktime(mstime(atime)), time.mktime(mstime(mtime))))

################################################################################

def check_sha1(sha1, entry, infile, start, end):
    """Check the SHA1 value of the specified range of the input file.

       @param sha1 the reported SHA1 value
       @param entry the id of the hash
       @param infile the input file to check
       @param start the start position
       @param end the end position
       @return string reporting if the hash is correct
    """

    infile.seek(start)
    found_sha1 = hashlib.sha1(infile.read(end - start))
    found_digest = found_sha1.digest()
    # SHA1 hashes are 20 bytes (160 bits) long
    ret = "SHA1 " + hex(entry) + " "
    if found_digest == sha1:
        return ret + "ok (" + found_sha1.hexdigest() + ")"
    else:
        hexdig = ""
        for i in sha1:
            if ord(i) < 10:
                val = "0"
            else:
                val = ""
            val += hex(i)[2:]
            hexdig += val
        return ret + "wrong (should be " + hexdig + " actual " + \
            found_sha1.hexdigest() + ")"

################################################################################

def get_cluster(startclust, offset):
    """get the real starting cluster"""
    rst = 0
    # BEGIN wxPirs
    while startclust >= 170:
        startclust //= 170
        rst += (startclust + 1) * offset
    # END wxPirs
    return rst

################################################################################

def fill_directory(infile, txtfile, contents, firstclust, makedir, start,
        offset):
    """Fill the directory structure with the files contained in the archive.

       @param infile pointer to the archive
       @param txtfile pointer to the resulting information text file
       @param contents contains the directory information
       @param firstclust address of the starting cluster of the first file in
              infile (in 4kB blocks, minus start bytes)
       @param makedir flag if directory should be filled, useful if only return
              is wanted
       @param start start of directory data
       @param offset increment for calculating real starting cluster
    """

    # dictionary which holds the directory structure,
    # patch 0xFFFF is the 'root' directory.
    paths = {0xFFFF:""}

    oldpathind = 0xFFFF # initial path, speed up file/dir creation

    for i in range(0x1000 * firstclust // 64):
        cur = contents[i * 64:(i + 1) * 64]
        if cur[40] == 0:
            # if filename length is zero, we're done
            break
        (outname, namelen, clustsize1, val1, clustsize2, val2, startclust,
            val3) = struct.unpack("<40sBHBHBHB", cur[0:50])
        # sizes and starting cluster are 24 bits long
        clustsize1 += val1 << 16
        clustsize2 += val2 << 16
        startclust += val3 << 16
        (pathind, filelen, dati1, dati2) = struct.unpack(">HLLL", cur[50:64])

        if not makedir:
            continue

        nlen = namelen & ~0xC0
        if nlen < 1 or nlen > 40:
            print("Filename length (%i) out of range, skipping file." % nlen)
            continue
        outname = outname[0:nlen].decode("utf-8") # strip trailing 0x00 from filename

        if txtfile != None:
            if namelen & 0x80 == 0x80:
                txtfile.write("Directory",)
            else:
                txtfile.write("File",)
            txtfile.write("name:" + outname)
            if namelen & 0x40 == 0x40:
                txtfile.write("Bit 6 of namelen is set.")

        if clustsize1 != clustsize2:
            print("Cluster sizes don't match (%i != %i), skipping file." % \
                (clustsize1, clustsize2))
            continue
        if startclust < 1 and namelen & 0x80 == 0:
            print("Starting cluster must be 1 or greater, skipping file.")
            continue
        if filelen > 0x1000 * clustsize1:
            print("File length (%i) is greater than the size in clusters " \
                "(%i), skipping file." % (filelen, clustsize1))
            continue

        if pathind != oldpathind:
            # working directory changed
            for _ in range(paths[oldpathind].count("/")):
                os.chdir("..") # go back to root directory
            os.chdir(paths[pathind])
            oldpathind = pathind
        if namelen & 0x80 == 0x80:
            # this is a directory
            paths[i] = paths[pathind] + outname + "/"
            do_mkdir(outname)
        else:
            # this is a file
            # space between files is set to 0x00
            adstart = startclust * 0x1000 + start
            if txtfile != None:
                txtfile.write("Starting: advertized" + hex(adstart))

            # block reading algorithm originally from wxPirs
            buf = b""
            while filelen > 0:
                realstart = adstart + get_cluster(startclust, offset)
                infile.seek(realstart)
                buf += infile.read(min(0x1000, filelen))
                startclust += 1
                adstart += 0x1000
                filelen -= 0x1000
            outfile = open(outname, "wb")
            outfile.write(buf,)
            outfile.close()

        do_utime(outname, dati2, dati1)

    # pop directory
    for _ in range(paths[oldpathind].count("/")):
        os.chdir("..")

################################################################################

def write_common_part(infile, txtfile, png2stop, start):
    """Writes out the common part of PIRS/LIVE and CON files.

       @param infile pointer to the PIRS/LIVE or CON file
       @param txtfile pointer to the resulting text file
       @param png2stop location where the second PNG image stops
                  (PIRS/LIVE : 0xB000, CON : 0xA000)
       @param start start of directory data, from wxPirs
    """

    infile.seek(0x32C)
    mhash = infile.read(20) # xbox180 : SHA1 hash of 0x0344-0xB000,
                            # CON : 0x0344 - 0xA000 (i.e. png2stop)
    (mentry_id, content_type) = struct.unpack(">LL", infile.read(8))

    if txtfile != None:
        print("\nMaster SHA1 hash :", \
            check_sha1(mhash, mentry_id, infile, 0x0344, png2stop), file=txtfile)
        txtfile.write("\nContent type" + hex(content_type) + ":")
        # content type list partially from V1kt0R
        # su20076000_00000000 has type 0x000b0000,
        # i.e. "Full game demo" & "Theme" ...
        if content_type == 0:
            txtfile.write("(no type)")
        elif content_type & 0x00000001:
            txtfile.write("Game save")
        elif content_type & 0x00000002:
            txtfile.write("Game add-on")
        elif content_type & 0x00030000:
            txtfile.write("Theme")
        elif content_type & 0x00090000:
            txtfile.write("Video clip")
        elif content_type & 0x000C0000:
            txtfile.write("Game trailer")
        elif content_type & 0x000D0000:
            txtfile.write("XBox Live Arcade")
        elif content_type & 0x00010000:
            txtfile.write("Gamer profile")
        elif content_type & 0x00020000:
            txtfile.write("Gamer picture")
        elif content_type & 0x00040000:
            txtfile.write("System update")
        elif content_type & 0x00080000:
            txtfile.write("Full game demo")
        else:
            txtfile.write("(unknown)")

        txtfile.write("\nDirectory data at (hex)" + hex(start))
        infile.seek(0x410)
        dump_info(infile, txtfile, "Titles")
        dump_info(infile, txtfile, "Descriptions")
        txtfile.write("\nPublisher:" +  strip_blanks(infile.read(0x80).decode("utf-8")) + "\n")
        txtfile.write("\nFilename:" + strip_blanks(infile.read(0x80).decode("utf-8")) + "\n")
    infile.seek(0x1710)
    (val1, png1len, png2len) = struct.unpack(">HLL", infile.read(10))
    if txtfile != None:
        txtfile.write("Value:" + str(val1))

    if png1len > 0:
        dump_png(infile, png1len, 0x571A - 0x171A, "1")

    if png2len > 0:
        infile.seek(0x571A)
        dump_png(infile, png2len, png2stop - 0x571A, "2")

    # entries are 64 bytes long
    # unused entries are set to 0x00
    infile.seek(start + 0x2F)
    (firstclust, ) = struct.unpack("<H", infile.read(2))

    infile.seek(start)
    buf = infile.read(0x1000 * firstclust)

    outname = os.path.basename(infile.name) + ".dir"
    makedir = nice_open_dir(outname)
    if makedir:
        print("Creating and filling content directory", outname)
        do_mkdir(outname)
        os.chdir(outname)
    if png2stop == 0xB000 and start == 0xC000:
        offset = 0x1000
    else:
        offset = 0x2000
    fill_directory(infile, txtfile, buf, firstclust, makedir, start, offset)

    # table of SHA1 hashes of payload
    if txtfile != None:
        print(file=txtfile)
        infile.seek(png2stop)
        buf = infile.read(start - png2stop)
        numempty = 0
        for i in range(len(buf) // 24):
            entry = buf[i * 24: i * 24 + 24]
            if entry.count(b"\0") < 24:
                if numempty > 0:
                    txtfile.write("\nEmpty entries:", numempty)
                    numempty = 0
                txtfile.write("Hash (hex):",)
                for j in range(20):
                    txtfile.write(hex(entry[j]))
                (j, ) = struct.unpack(">L", entry[20:24])
                txtfile.write("\nEntry id:" +  hex(j))
            else:
                numempty += 1

        txtfile.write("\nTrailing data (hex):")
        for i in buf[len(buf) - (len(buf) % 24):]:
            txtfile.write(hex(i))
        print(file=txtfile)

        txtfile.close()

################################################################################

def handle_live_pirs(infile, fsize):
    """LIVE and PIRS files are archive files.
       They contain a certificate, payload, SHA1 checksums,
       2 icons, textual information, and the files themselves.

       @param infile pointer to the archive file
       @param fsize size of infile
    """

    print("Handling LIVE/PIRS file.")

    if not check_size(fsize, 0xD000):
        return

    txtfile = open_info_file(infile)
    if txtfile != None:
        txtfile.write("Certificate (hex):",)
        cert = infile.read(0x100)
        for i in cert:
            txtfile.write(hex(i),)

        txtfile.write("\n\nData (hex):",)
        data = infile.read(0x228)
        for i in data:
            txtfile.write(hex(i),)
        print(file=txtfile)

    ### BEGIN wxPirs ###
    infile.seek(0xC032) # originally 4 bytes at 0xC030
    (pathind, ) = struct.unpack(">H", infile.read(2))
    if pathind == 0xFFFF:
        start  = 0xC000
    else:
        start  = 0xD000
    ### END wxPirs ###
    write_common_part(infile, txtfile, 0xB000, start)

################################################################################

def handle_con(infile, fsize):
    """Handle CON files, they are similar to LIVE/PIRS files.

       @param infile pointer to the archive file
       @param fsize size of infile
    """

    print("Handling CON file.")

    # string "3X80345-001" at 0x000A
    # string "12-07-05" at 0x0020

    if not check_size(fsize, 0xD000):
        return

    txtfile = open_info_file(infile)
    if txtfile != None:
        txtfile.write("(Console specific) header (hex):",)
        data = infile.read(0x1A8)
        for i in data:
            txtfile.write(hex(i),)

        txtfile.write("\n\nFile specific data (hex):",)
        data = infile.read(388)
        for i in data:
            txtfile.write(hex(i),)

    write_common_part(infile, txtfile, 0xA000, 0xC000)

################################################################################

def handle_fmim(infile, fsize):
    """FMIM files are WMA files encoded in WMA 9.1, 192 kb/s, 44100 Hz, stereo,
       1-pass CBR, unclassified, unprotected, and prefixed with a custom header.

       @param infile pointer to the FMIM file.
       @param size size of infile
    """

    print("Handling FMIM file.")

    if not check_size(fsize, 3136):
        return

    # check for common/standard pattern
    pattern = (0, 0, 0, 1, 0, 1, 0, 1)
    buf = struct.unpack("8B", infile.read(8))
    if buf != pattern:
        print("Signature ", buf, " does not match ", pattern)
        return

    # Dump information into .txt file
    txtfile = open_info_file(infile)
    if txtfile != None:
        txtfile.write("Song:", strip_blanks(infile.read(0x200)))
        txtfile.write("Album:", strip_blanks(infile.read(0x200)))
        txtfile.write("Artist 1:", strip_blanks(infile.read(0x200)))
        txtfile.write("Artist 2:", strip_blanks(infile.read(0x200)))
        txtfile.write("Genre 1:", strip_blanks(infile.read(0x200)))
        txtfile.write("Genre 2:", strip_blanks(infile.read(0x200)))
        # 4 byte "size" info, followed by 248 0-bytes
        txtfile.write("Size:", struct.unpack(">L", infile.read(4))[0])
        zerobuf = infile.read(0xF8)
        if False in [x == '\0' for x in zerobuf]:
            txtfile.write("Not followed by 248 0-bytes:",)
            for i in zerobuf:
                txtfile.write(hex(i),)
            print(file=txtfile)
        txtfile.close()

    # Dump WMA into .wma file
    wmaname = os.path.basename(infile.name) + ".wma"
    if nice_open_file(wmaname):
        buf = infile.read() # read until EOF
        print("Writing WMA file", wmaname)
        wmafile = open(wmaname, "wb")
        wmafile.write(buf,)
        wmafile.close()

################################################################################

def handle_xuiz(infile, fsize):
    """XUIZ (.xzp) support.

       @param infile pointer to the XUIZ file
       @param fsize size of the XUIZ file
    """

    print("Handling XUIZ file")

    # information partially from http://ch2r.com/wiki/.xzp

    txtfile = open_info_file(infile)
    (xui_flags, xui_len, xui_smth, xui_data_ptr, xui_num_de) = \
        struct.unpack(">LLLLH", infile.read(18))
    if txtfile != None:
        txtfile.write("Flags: ", xui_flags)
        txtfile.write("Size: ", xui_len)
        txtfile.write("? : ", xui_smth)
        txtfile.write("Data pointer: ", xui_data_ptr)
        txtfile.write("Directory entries: ", xui_num_de)

    if fsize != xui_len:
        print("Size mismatch: expected ", xui_len, " got ", fsize)
        return

    buf = infile.read(xui_data_ptr)
    bufpos = 0

    for dirent in range(xui_num_de):
        if txtfile != None:
            txtfile.write("\nEntry ", dirent)
            (flen, fptr, fnlen) = struct.unpack(">LLB", buf[bufpos:bufpos + 9])
            bufpos += 9
            txtfile.write("File length: ", flen)
            txtfile.write("File start: ", fptr)
            txtfile.write("Filename length (UTF-16): ", fnlen)
            filename = rm_nul(strip_blanks(buf[bufpos:bufpos + 2 * fnlen]))
            bufpos += 2 * fnlen
            txtfile.write("Filename: ", filename)
        infile.seek(22 + xui_data_ptr + fptr)
        dir_count = 0
        for i in filename.split("\\")[:-1]:
            do_mkdir(i)
            os.chdir(i)
            dir_count += 1
        outfile = open(filename.split("\\")[-1], "wb")
        outfile.write(infile.read(flen))
        outfile.close()
        for _ in range(dir_count):
            os.chdir("..")

################################################################################

if __name__ == "__main__":
    import hashlib # requires Python 2.5+
    import os
    import struct
    import sys
    import time

    lang = ["English", "Japanese", "German", "French", "Spanish", "Italian",
            "Korean", "Chinese", "Portuguese"]

    if len(sys.argv) != 2:
        print("usage: PYTHON extract360.py filename")
    else:
        inputfile = open(sys.argv[1], "rb")

        filesize = os.path.getsize(inputfile.name)

        sig = inputfile.read(4).decode('utf-8')
        if sig in ["LIVE", "PIRS"]:
            handle_live_pirs(inputfile, filesize)
        elif sig == "CON ":
            handle_con(inputfile, filesize)
        elif sig == "FMIM":
            handle_fmim(inputfile, filesize)
        elif sig == "XUIZ":
            handle_xuiz(inputfile, filesize) # aka .xzp files
        else:
            print("Unknown signature: ", sig)

        inputfile.close()

