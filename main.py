import discord
from discord.ext import commands
import logging
import requests
import sqlalchemy as sqa
import sqlalchemy.orm as orm
from PIL import Image, ImageDraw
from io import BytesIO
import colorsys
import json

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

TOKEN = "MTIyOTg0NjY2MzUzNjA1NDM4Ng.GI7oWT.aDfQdR_zqr8Bamr7K06xpYHF3eCFGJkmLR8Jhc"

SqlAlchemyBase = orm.declarative_base()


class Palette(SqlAlchemyBase):
    __tablename__ = 'color_palettes'

    id = sqa.Column(sqa.Integer, primary_key=True, autoincrement=True)
    name = sqa.Column(sqa.String, nullable=True, unique=True)
    color_list = sqa.Column(sqa.String, nullable=True)
    tag = sqa.Column(sqa.Boolean)


engine = sqa.create_engine(f'sqlite:///db/kakmnebot.db?check_same_thread=False')

session = orm.sessionmaker()
session.configure(bind=engine)
SqlAlchemyBase.metadata.create_all(engine)

s = session()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix='!', intents=intents)

g_last_color = json.dumps([0, 0, 0])


async def on_ready(self):
    logger.info(f'{self.user} has connected to Discord!')
    for guild in self.guilds:
        logger.info(f'{self.user} подключились к чату:\n'
                    f'{guild.name}(id: {guild.id})')


help_dict = {"!save": "Сохраняет последний цвет, полученный из картинки, по названию",
             "!add": "Добавляет новый цвет по его названию и значениям rgb",
             "!tag": "Помечает цвет/палитру по названию",
             "!untag": "Снимает метку с цвета/палитры по названию",
             "!delete": "Удаляет цвет/палитру по названию",
             "!colormind": "Дополняет цвет до палитры из пяти цевтов по названию, обращаясь к Colormind-API",
             "!list": "Выводит перечень имеющихся цветов и палитр, начиная с помеченных"}


@client.command()
async def help_me_please(self, command="all"):
    global g_last_color
    if command == "all":
        await self.channel.send("Перечень команд для работы с ботом:")
        for command in help_dict:
            await self.channel.send(f"{command}: {help_dict[command]}")
    else:
        if help_dict[command]:
            await self.channel.send(f"{command}: {help_dict[command]}")


@client.event
async def on_message(message):
    global g_last_color
    if message.attachments:
        attachment = message.attachments[0]
        image_url = attachment.url
        responce = requests.get(image_url)
        img = Image.open(BytesIO(responce.content))

        x, y = img.size
        sats = []
        lums = []
        hues_count = []
        for i in range(361):
            sats.append(0)
            lums.append(0)
            hues_count.append(0)
        pixels = img.load()
        if len(pixels[0, 0]) < 3:
            await message.channel.send("цвета не найдены")
            return
        for i in range(x):
            for j in range(y):
                p = pixels[i, j]
                r, g, b = p[0], p[1], p[2]
                h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
                h = int(h * 360)
                s = int(s * 100)
                l = int(l * 100)
                sats[h] += s
                lums[h] += l
                hues_count[h] += 1
        max_hue = max(hues_count)
        hue = hues_count.index(max_hue)
        sat = sats[hue] / hues_count[hue]
        lum = lums[hue] / hues_count[hue]
        h = hue / 360
        s = sat / 100
        l = lum / 100
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        red = int(r * 255)
        green = int(g * 255)
        blue = int(b * 255)

        histogram_image = Image.new("RGB", (360, 100), (0, 0, 0))
        draw = ImageDraw.Draw(histogram_image)
        for i in range(360):
            level = hues_count[i] * 100 // max_hue
            ht = i / 360
            st = sats[i] / 100 / (hues_count[i] + 1)
            lt = lums[i] / 100 / (hues_count[i] + 1)
            print(ht, st, lt)
            r, g, b = colorsys.hls_to_rgb(ht, lt, st)
            print(r, g, b)
            draw.line((i, 100, i, 100-level), fill=(int(r*100), int(g*100), int(b*100)))
        histogram_image.save("thumbnail.png")
        thumbfile = discord.File("thumbnail.png", filename="thumbnail.png")
        embed = discord.Embed(title="Гистограмма:")
        embed.set_image(url="attachment://thumbnail.png")
        embed.colour = 0x00ff00
        await message.channel.send(file=thumbfile, embed=embed)


        main_image = Image.new("RGB", (100, 100), (red, green, blue))

        embed = discord.Embed(title="основной оттенок:")
        clhex = f'[{red}, {green}, {blue}]'
        main_image.save("thumbnail.png")
        thumbfile = discord.File("thumbnail.png", filename="thumbnail.png")
        embed.add_field(name="", value=clhex, inline=False)
        embed.set_image(url="attachment://thumbnail.png")
        embed.colour = 0x00ff00
        await message.channel.send(file=thumbfile, embed=embed)
        g_last_color = json.dumps([[red, green, blue]])
    await client.process_commands(message)


@client.command()
async def save(context, name="мой любимый цвет"):
    global g_last_color
    await context.channel.send(f'сохраняем последний цвет как {name}')
    color_name_check = s.query(Palette).filter(Palette.name == name).first()
    if color_name_check:
        await context.channel.send(f'цвет {name} уже сохранен')
        return
    else:
        s.add(Palette(name=name, color_list=g_last_color, tag=False))
        s.commit()


@client.command()
async def add(context, name="мой любимый цвет", r=255, g=255, b=255):
    global g_last_color
    await context.channel.send(f'Добавляем цвет {r}, {g}, {b} как {name}')
    color_name_check = s.query(Palette).filter(Palette.name == name).first()
    if color_name_check:
        await context.channel.send(f'цвет {name} уже сохранен')
        return
    else:
        s.add(Palette(name=name, color_list=json.dumps([[r, g, b]])))
        s.commit()


@client.command()
async def tag(context, name="мой любимый цвет"):
    global g_last_color
    await context.channel.send(f'Помечаем цвет {name}')
    color_name_check = s.query(Palette).filter(Palette.name == name).first()
    if not color_name_check:
        await context.channel.send(f'Цвет {name} не найден')
        return
    else:
        if color_name_check.tag:
            await context.channel.send(f'Цвет {name} уже помечен')
        else:
            color_name_check.tag = True
            s.commit()


@client.command()
async def untag(context, name="мой любимый цвет"):
    global g_last_color
    await context.channel.send(f'Снимаем пометку с цвета {name}')
    color_name_check = s.query(Palette).filter(Palette.name == name).first()
    if not color_name_check:
        await context.channel.send(f'Цвет {name} не найден')
        return
    else:
        if not color_name_check.tag:
            await context.channel.send(f'Цвет {name} не помечен')
        else:
            color_name_check.tag = False
            s.commit()


@client.command()
async def delete(context, name="мой любимый цвет"):
    global g_last_color
    await context.channel.send(f'удаляем цвет {name}')
    color_name_check = s.query(Palette).filter(Palette.name == name).first()
    if not color_name_check:
        await context.channel.send(f'цвет {name} не найден')
        return
    else:
        s.delete(color_name_check)
        s.commit()


@client.command()
async def colormind(context, name="мой любимый цвет"):
    await context.channel.send(f'запрашиваем ColorMind для расширения палитры {name}')
    color_name_check = s.query(Palette).filter(Palette.name == name).first()
    if not color_name_check:
        await context.channel.send(f'цвет {name} не найден')
        return
    else:
        colors = json.loads(color_name_check.color_list)
        request_colors = [colors[0], "N", "N", "N", "N"]
        data = {"model": "default", "input": request_colors}
        responce = requests.post("http://colormind.io/api/", data=json.dumps(data))
        results = json.loads(responce.content)
        color_name_check = s.query(Palette).filter(Palette.name == name).first()
        color_name_check.color_list = json.dumps(results["result"])
        s.commit()


@client.command()
async def list(context):
    color_name_check = s.query(Palette).filter(Palette.tag==True).all()
    for color in color_name_check:
        embed = discord.Embed(title=color.name)
        new_image = Image.new("RGB", (500, 100), (0, 0, 0))
        draw = ImageDraw.Draw(new_image)
        packed = color.color_list
        color_list = json.loads(packed)
        for i in range(len(color_list)):
            if len(color_list[i]) == 3:
                draw.rectangle((i*100, 0, i * 100 + 99, 99),
                               fill=(color_list[i][0], color_list[i][1], color_list[i][2]))
        new_image.save("thumbnail.png")
        thumbfile = discord.File("thumbnail.png", filename="thumbnail.png")
        embed.set_image(url="attachment://thumbnail.png")
        await context.channel.send(file=thumbfile, embed=embed)

    color_name_check = s.query(Palette).filter(Palette.tag==False).all()
    for color in color_name_check:
        embed = discord.Embed(title=color.name)
        new_image = Image.new("RGB", (250, 50), (0, 0, 0))
        draw = ImageDraw.Draw(new_image)
        packed = color.color_list
        color_list = json.loads(packed)
        for i in range(len(color_list)):
            if len(color_list[i]) == 3:
                draw.rectangle((i*50, 0, i * 50 + 49, 49),
                               fill=(color_list[i][0], color_list[i][1], color_list[i][2]))
        new_image.save("thumbnail.png")
        thumbfile = discord.File("thumbnail.png", filename="thumbnail.png")
        embed.set_image(url="attachment://thumbnail.png")
        await context.channel.send(file=thumbfile, embed=embed)

client.run(TOKEN)
