from machine import Pin, SoftI2C
import ssd1306plus, time

gc.collect()

i2c = SoftI2C(scl=Pin(6), sda=Pin(5))

oled_width = 128
oled_height = 64
oled = ssd1306plus.SSD1306_I2C(oled_width, oled_height, i2c)

oled.fill(0)

# oled.fill_rect(X, Y, Width, Height, Color)
oled.fill_rect(0, 0, 128, 16, 1)

# oled.scaled(Text, X, Y, Scale, Color)
oled.scaled("Hello", 0, 1, 2, 0)
oled.scaled("Hi", 0, 24, 3, 1)

# oled.text(Text, X, Y, Color)
oled.text('ohai', 0, 54, 1)

# oled.rect(X0, Y0, X1, Y1, Color) 
oled.rect(50, 20, 50, 40, 1)
oled.fill_rect(60, 30, 30, 20, 1)

# oled.hline(X, Y, Width, Color)
# oled.vline(X, Y, Height, Color)
# oled.line(X0, Y0, X1, Y1, Color)
oled.hline(105, 30, 16, 1)
oled.vline(113, 30, 14, 1)
oled.line(105, 30, 113, 50, 1)
oled.line(121, 30, 113, 50, 1) 

oled.show()

time.sleep(1)

#render single or multi frame .gif files uploaded with the script
#oled.gif("name.gif", x=XPOS, y=YPOS, loop=Number of loops (-1 = Forever)-)
#use `delay_ms` to override frame delay, set to `None` to use gif's native delay
#redraw every frame with clear=True
#crop [XMIN,YMIN,XMAX,YMAX]
oled.gif("eye.gif", x=30, y=20, loop=1, clear=True)
oled.gif("eye.gif", x=30, y=20, loop=1, clear=True, crop=[70,0,100,100])
oled.gif("eye.gif", x=30, y=20, loop=-1)



# Other standard stuff like pixel, framebuf, scroll etc. supported
