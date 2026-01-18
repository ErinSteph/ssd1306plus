from machine import Pin, SoftI2C
import ssd1306plus

i2c = SoftI2C(scl=Pin(5), sda=Pin(18))

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
# oled.hline(X, Y, Height, Color)
# oled.hline(X, Y, Height, Color)
oled.hline(105, 30, 16, 1)
oled.vline(113, 30, 14, 1)
oled.line(105, 30, 113, 50, 1)
oled.line(121, 30, 113, 50, 1) 

oled.show()

# Other standard stuff like pixel, framebuf, scroll etc. supported