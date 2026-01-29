# ssd1306plus - extended I2C and SPI SSD1306 oled driver
# v1.2.0 - GIF cropping, garbage collection
# v1.1.0 - added GIF support
# v1.0.0 - initial

from micropython import const
import framebuf, gc


# register definitions
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_IREF_SELECT = const(0xAD)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)

# Subclassing FrameBuffer provides support for graphics primitives
# http://docs.micropython.org/en/latest/pyboard/library/framebuf.html
class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP,  # display off
            # address setting
            SET_MEM_ADDR,
            0x00,  # horizontal
            # resolution and layout
            SET_DISP_START_LINE,  # start at line 0
            SET_SEG_REMAP | 0x01,  # column addr 127 mapped to SEG0
            SET_MUX_RATIO,
            self.height - 1,
            SET_COM_OUT_DIR | 0x08,  # scan from COM[N] to COM0
            SET_DISP_OFFSET,
            0x00,
            SET_COM_PIN_CFG,
            0x02 if self.width > 2 * self.height else 0x12,
            # timing and driving scheme
            SET_DISP_CLK_DIV,
            0x80,
            SET_PRECHARGE,
            0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL,
            0x30,  # 0.83*Vcc
            # display
            SET_CONTRAST,
            0xFF,  # maximum
            SET_ENTIRE_ON,  # output follows RAM contents
            SET_NORM_INV,  # not inverted
            SET_IREF_SELECT,
            0x30,  # enable internal IREF during display on
            # charge pump
            SET_CHARGE_PUMP,
            0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,  # display on
        ):  # on
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def rotate(self, rotate):
        self.write_cmd(SET_COM_OUT_DIR | ((rotate & 1) << 3))
        self.write_cmd(SET_SEG_REMAP | (rotate & 1))
        
        
    def gif(self, filename, x=0, y=0, loop=1, delay_ms=None, clear=False, crop=None):
        """
        - filename: path to .gif file on the filesystem
        - x, y: offset of the GIF's logical screen on the display
        - loop: number of times to loop; use -1 for infinite
        - delay_ms: override frame delay (ms). If None, use GIF's own delay.
        - clear: if True, clear the frame area before drawing each frame
        - Supports non-interlaced GIFs only.
        - Blocking: does not return until all loops are done.
        """
        import time

        # Read entire GIF file
        with open(filename, "rb") as f:
            data = f.read()

        if len(data) < 13:
            return

        # Header: "GIF87a" or "GIF89a"
        if not (data.startswith(b"GIF87a") or data.startswith(b"GIF89a")):
            return

        # Logical Screen Descriptor
        ls_width  = data[6] | (data[7] << 8)
        ls_height = data[8] | (data[9] << 8)
        packed    = data[10]
        bg_color_index = data[11]
        # pixel_aspect = data[12]  # not used

        # Global Color Table
        gct_flag = (packed & 0x80) != 0
        gct_size = 0
        global_color_table = None

        p = 13  # position after header + LSD
        if gct_flag:
            gct_size = 1 << ((packed & 0x07) + 1)
            gct_bytes = 3 * gct_size
            global_color_table = data[p:p + gct_bytes]
            p += gct_bytes

        # Helper: read GIF sub-blocks into one bytes object
        def _read_subblocks(pos):
            img_data = bytearray()
            length = len(data)
            while pos < length:
                block_len = data[pos]
                pos += 1
                if block_len == 0:
                    break
                img_data.extend(data[pos:pos + block_len])
                pos += block_len
            return bytes(img_data), pos

        # Helper: LZW decode the image data into colour indices
        def _lzw_decode(img_bytes, min_code_size, expected_pixels):
            # Simple GIF LZW decoder, up to 12-bit codes
            if min_code_size < 2 or min_code_size > 8:
                # Fallback: just truncate raw bytes
                return list(img_bytes[:expected_pixels])

            clear_code = 1 << min_code_size
            end_code = clear_code + 1
            code_size = min_code_size + 1
            max_code_size = 12

            # Dictionary: code -> [indices...]
            dictionary = [[i] for i in range(clear_code)] + [None, None]

            bit_pos = 0
            data_len = len(img_bytes)
            output = []
            prev = None

            def _next_code(bit_pos, code_size):
                byte_pos = bit_pos >> 3
                if byte_pos >= data_len:
                    return None, bit_pos
                raw = 0
                bits_read = 0
                shift = 0
                while bits_read < code_size and byte_pos < data_len:
                    b = img_bytes[byte_pos]
                    available = 8 - (bit_pos & 7)
                    take = code_size - bits_read
                    if take > available:
                        take = available
                    mask = (1 << take) - 1
                    v = (b >> (bit_pos & 7)) & mask
                    raw |= v << shift
                    bits_read += take
                    shift += take
                    bit_pos += take
                    byte_pos = bit_pos >> 3
                if bits_read != code_size:
                    return None, bit_pos
                return raw, bit_pos

            # Initial code
            code, bit_pos = _next_code(bit_pos, code_size)
            if code is None:
                return output

            if code == clear_code:
                dictionary = [[i] for i in range(clear_code)] + [None, None]
                code_size = min_code_size + 1
                code, bit_pos = _next_code(bit_pos, code_size)
                if code is None or code == end_code:
                    return output

            if code == end_code:
                return output
            if code >= len(dictionary) or dictionary[code] is None:
                return output

            prev = dictionary[code][:]
            output.extend(prev)

            while len(output) < expected_pixels:
                code, bit_pos = _next_code(bit_pos, code_size)
                if code is None:
                    break

                if code == clear_code:
                    dictionary = [[i] for i in range(clear_code)] + [None, None]
                    code_size = min_code_size + 1
                    code, bit_pos = _next_code(bit_pos, code_size)
                    if code is None or code == end_code:
                        break
                    if code >= len(dictionary) or dictionary[code] is None:
                        cur = []
                    else:
                        cur = dictionary[code][:]
                    output.extend(cur)
                    prev = cur[:]
                    continue

                if code == end_code:
                    break

                if code < len(dictionary) and dictionary[code] is not None:
                    cur = dictionary[code][:]
                elif code == len(dictionary):
                    # KwKwK case
                    cur = prev[:] + [prev[0]]
                else:
                    # Invalid code
                    break

                output.extend(cur)
                dictionary.append(prev[:] + [cur[0]])
                
                if len(dictionary) == (1 << code_size) and code_size < max_code_size:
                    code_size += 1

                prev = cur[:]

            return output[:expected_pixels]

        # Animation loop
        loops_done = 0
        infinite = loop < 0
        start_pos = p  # where the blocks start

        while infinite or loops_done < loop:
            p = start_pos
            transparency_index = None
            frame_delay_ms = 0

            while p < len(data):
                block_type = data[p]
                p += 1

                # Trailer: end of GIF
                if block_type == 0x3B:
                    break

                # Extension block
                if block_type == 0x21:
                    label = data[p]
                    p += 1

                    # Graphics Control Extension (gives us delay + transparency)
                    if label == 0xF9:
                        block_size = data[p]
                        p += 1
                        if block_size == 4:
                            packed_fields = data[p]
                            p += 1
                            delay_lo = data[p]
                            delay_hi = data[p + 1]
                            p += 2
                            trans_index = data[p]
                            p += 1
                            terminator = data[p]
                            p += 1

                            frame_delay_ms = (delay_hi << 8 | delay_lo) * 10
                            if frame_delay_ms <= 0:
                                frame_delay_ms = 50  # sensible default

                            if packed_fields & 0x01:
                                transparency_index = trans_index
                        else:
                            # Skip odd GCE sizes
                            sub_len = data[p]
                            p += 1 + sub_len
                            while sub_len:
                                sub_len = data[p]
                                p += 1 + sub_len

                    else:
                        # Skip other extension types
                        sub_len = data[p]
                        p += 1
                        while sub_len:
                            p += sub_len
                            sub_len = data[p]
                            p += 1

                    continue

                # Image Descriptor
                if block_type == 0x2C:
                    left = data[p] | (data[p + 1] << 8)
                    top = data[p + 2] | (data[p + 3] << 8)
                    width = data[p + 4] | (data[p + 5] << 8)
                    height = data[p + 6] | (data[p + 7] << 8)
                    packed_fields = data[p + 8]
                    p += 9

                    lct_flag = (packed_fields & 0x80) != 0
                    interlace = (packed_fields & 0x40) != 0

                    # Interlaced GIFs not supported: skip them
                    if interlace:
                        if lct_flag:
                            lct_size = 1 << ((packed_fields & 0x07) + 1)
                            p += 3 * lct_size
                        # skip image sub-blocks
                        _, p = _read_subblocks(p + 1)
                        continue

                    local_color_table = None
                    if lct_flag:
                        lct_size = 1 << ((packed_fields & 0x07) + 1)
                        lct_bytes = 3 * lct_size
                        local_color_table = data[p:p + lct_bytes]
                        p += lct_bytes

                    lzw_min_code_size = data[p]
                    p += 1

                    img_bytes, p = _read_subblocks(p)
                    expected_pixels = width * height
                    indices = _lzw_decode(img_bytes, lzw_min_code_size, expected_pixels)

                    # Draw the frame
                    if clear:
                        self.fill_rect(x + left, y + top, width, height, 0)

                    pos = 0
                    bg_idx = bg_color_index  # for our 1-bit mapping

                    for yy in range(height):
                        for xx in range(width):
                            if pos >= len(indices):
                                break
                            idx = indices[pos]
                            pos += 1

                            if (transparency_index is not None) and (idx == transparency_index):
                                # Leave existing pixel as-is
                                continue

                            col = 0
                            if idx != bg_idx:
                                col = 1
                            notCropped = True
                            if crop is not None:
                                if (x + left + xx) < crop[0] or (x + left + xx) >  crop[2]:
                                    notCropped = False
                                if (y + top + yy) < crop[1] or (y + top + yy) >  crop[3]:
                                    notCropped = False
                            if notCropped == True:
                                
                                self.pixel(x + left + xx, y + top + yy, col)
                            

                    self.show()
                    
                    # Frame delay: override if user provided delay_ms
                    d = delay_ms if (delay_ms is not None) else frame_delay_ms
                    if d <= 0:
                        d = 50
                    time.sleep_ms(d)

                    continue
            gc.collect()
            loops_done += 1
            
            
    def play_gif(self, filename, x=0, y=0, loop=1, delay_ms=None, clear=False, crop=None):
        return self.gif(filename, x, y, loop, delay_ms, clear, crop)


    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width != 128:
            # narrow displays use centred columns
            col_offset = (128 - self.width) // 2
            x0 += col_offset
            x1 += col_offset
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b"\x40", None]  # Co=0, D/C#=1
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)
        
    def scaled(self, text, x, y, scale=2, colr=1):
        clr = 0
        temp_w = len(text) * 8
        temp_h = 8
        temp_buf = bytearray((temp_w // 8) * temp_h)
        temp_fb = framebuf.FrameBuffer(temp_buf, temp_w, temp_h, framebuf.MONO_HLSB)
        temp_fb.fill(0)
        temp_fb.text(text, 0, 0)
        
        for ix in range(temp_w):
            for iy in range(temp_h):
                if temp_fb.pixel(ix, iy):
                    x0 = x + ix * scale
                    y0 = y + iy * scale
                    # draw block
                    for dx in range(scale):
                        for dy in range(scale):
                            self.pixel(x0 + dx, y0 + dy, colr)


class SSD1306_SPI(SSD1306):
    def __init__(self, width, height, spi, dc, res, cs, external_vcc=False):
        self.rate = 10 * 1024 * 1024
        dc.init(dc.OUT, value=0)
        res.init(res.OUT, value=0)
        cs.init(cs.OUT, value=1)
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        import time

        self.res(1)
        time.sleep_ms(1)
        self.res(0)
        time.sleep_ms(10)
        self.res(1)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(buf)
        self.cs(1)
        
    def scaled(self, text, x, y, scale=2, colr=1):
        clr = 0
        temp_w = len(text) * 8
        temp_h = 8
        temp_buf = bytearray((temp_w // 8) * temp_h)
        temp_fb = framebuf.FrameBuffer(temp_buf, temp_w, temp_h, framebuf.MONO_HLSB)
        temp_fb.fill(0)
        temp_fb.text(text, 0, 0)
        
        for ix in range(temp_w):
            for iy in range(temp_h):
                if temp_fb.pixel(ix, iy):
                    x0 = x + ix * scale
                    y0 = y + iy * scale
                    # draw block
                    for dx in range(scale):
                        for dy in range(scale):
                            self.pixel(x0 + dx, y0 + dy, colr)
