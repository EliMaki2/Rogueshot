class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.magnitude = (self.x**2 + self.y**2) ** 0.5

    def add(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def subtract(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def multiply(self, scalar):
        return Vector(self.x * scalar, self.y * scalar)

    def normalize(self):
        if self.magnitude == 0:
            return Vector(0, 0)
        return Vector(self.x / self.magnitude, self.y / self.magnitude)
    
class RGB_Color:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
    
    def to_tuple(self):
        return (self.r, self.g, self.b)

    def brighten(self, value):
        return RGB_Color(min(int(self.r * value), 255),
                         min(int(self.g * value), 255),
                         min(int(self.b * value), 255))
