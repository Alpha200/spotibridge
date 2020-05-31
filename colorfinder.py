from math import sqrt


def color_filter_hue(r, g, b):
    return (abs(r - g) * abs(r - g) + abs(r - b) * abs(r - b) + abs(g - b) * abs(g - b)) / 65535 * 50 + 1


def color_filter_hue_brightness(r, g, b):
    v = max(r / 255, g / 255, b / 255)
    return (((abs(r - g) * abs(r - g) + abs(r - b) * abs(r - b) + abs(g - b) * abs(g - b)) / 65535 * 50) + 1) * sqrt(v)


class ColorFinder:
    def __init__(self, color_filter):
        self.color_filter = color_filter

    def get_most_prominent_color(self, image):
        rgb = None
        image_data = self.get_image_data(image)

        for degrade in (6, 4, 2, 0):
            rgb = self.get_most_prominent_rgb(image_data, degrade, rgb)

        return rgb['r'], rgb['g'], rgb['b']

    @staticmethod
    def does_rgb_match(rgb, pixel):
        if rgb is None:
            return True

        r = pixel['r'] >> rgb['degrade']
        g = pixel['g'] >> rgb['degrade']
        b = pixel['b'] >> rgb['degrade']

        return r == rgb['r'] and g == rgb['g'] and b == rgb['b']

    def get_most_prominent_rgb(self, pixels, degrade, rgb_match):
        result = dict(r=0, g=0, b=0, count=0, degrade=degrade)
        db = dict()

        for pixel in pixels.values():
            total_weight = pixel['weight'] * pixel['count']

            if self.does_rgb_match(rgb_match, pixel):
                pixel_group_key = "{},{},{}".format(pixel['r'] >> degrade, pixel['g'] >> degrade, pixel['b'] >> degrade)

                if pixel_group_key not in db:
                    db[pixel_group_key] = total_weight
                else:
                    db[pixel_group_key] += total_weight

        for k, v in db.items():
            if v > result['count']:
                r, g, b = tuple(int(value) for value in k.split(','))
                result = dict(r=r, g=g, b=b, count=v, degrade=degrade)

        return result

    def get_image_data(self, image):
        result = dict()
        length = image.width * image.height
        factor = max(1, round(length / 1250.0))

        for idx in range(0, length, factor):
            r, g, b = image.getpixel((int(idx / image.width), idx % image.width))

            key = '{},{},{}'.format(r, g, b)

            if key not in result:
                entry = dict(r=r, g=g, b=b, count=1, weight=self.color_filter(r, g, b))

                if entry['weight'] <= 0:
                    entry['weight'] = 1e-10

                result[key] = entry
            else:
                result[key]['count'] += 1

        return result
