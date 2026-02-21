import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import os

TOKEN=os.environ["TOKEN"]

intents=discord.Intents.default()
bot=commands.Bot(command_prefix="!",intents=intents)

conn=sqlite3.connect("schedule.db")
c=conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS schedule(time TEXT,user_id TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS config(key TEXT,value TEXT)")
conn.commit()

def get_log():
    c.execute("SELECT value FROM config WHERE key='log'")
    r=c.fetchone()
    return int(r[0]) if r else None

# ===== ボタン =====
class TimeButton(discord.ui.Button):
    def __init__(self,time):
        super().__init__(label=time,row=0,style=discord.ButtonStyle.primary)
        self.time=time

    async def async def callback(self,interaction:discord.Interaction):
    uid=str(interaction.user.id)

    # その時間の予約取得
    c.execute("SELECT user_id FROM schedule WHERE time=?",(self.time,))
    row=c.fetchone()

    log=get_log()
    log_ch=interaction.guild.get_channel(log) if log else None

    # ===== 予約なし =====
    if not row:
        c.execute("INSERT INTO schedule VALUES (?,?)",(self.time,uid))
        conn.commit()

        self.label=f"{self.time} ({interaction.user.display_name})"
        self.style=discord.ButtonStyle.success

        if log_ch:
            await log_ch.send(f"{interaction.user.mention} が {self.time} 予約")

    # ===== 本人ならキャンセル =====
    elif row[0]==uid:
        c.execute("DELETE FROM schedule WHERE time=?",(self.time,))
        conn.commit()

        self.label=self.time
        self.style=discord.ButtonStyle.primary

        if log_ch:
            await log_ch.send(f"{interaction.user.mention} が {self.time} キャンセル")

    # ===== 他人が予約済み =====
    else:
        await interaction.response.send_message("すでに予約済み",ephemeral=True)
        return

    await interaction.response.edit_message(view=self.view)(self,interaction:discord.Interaction):
        uid=str(interaction.user.id)

        c.execute("SELECT * FROM schedule WHERE time=? AND user_id=?",(self.time,uid))
        exist=c.fetchone()

        log=get_log()
        log_ch=interaction.guild.get_channel(log) if log else None

        if exist:
            c.execute("DELETE FROM schedule WHERE time=? AND user_id=?",(self.time,uid))
            conn.commit()
            self.label=self.time
            self.style=discord.ButtonStyle.primary
            if log_ch:
                await log_ch.send(f"{interaction.user.mention} が {self.time} キャンセル")
        else:
            c.execute("INSERT INTO schedule VALUES (?,?)",(self.time,uid))
            conn.commit()
            self.label=f"{self.time} ({interaction.user.display_name})"
            self.style=discord.ButtonStyle.success
            if log_ch:
                await log_ch.send(f"{interaction.user.mention} が {self.time} 予約")

        await interaction.response.edit_message(view=self.view)

# ===== View =====
class TimeView(discord.ui.View):
    def __init__(self,times):
        super().__init__(timeout=None)
        for t in times:
            self.add_item(TimeButton(t))

# ===== schedule =====
@bot.tree.command(name="schedule")
@app_commands.describe(start="開始",end="終了",interval="分")
async def schedule(interaction:discord.Interaction,start:str,end:str,interval:int):

    s=datetime.strptime(start,"%H:%M")
    e=datetime.strptime(end,"%H:%M")
    if e<=s:
        e+=timedelta(days=1)

    times=[]
    while s<=e:
        times.append(s.strftime("%H:%M"))
        s+=timedelta(minutes=interval)

    embed=discord.Embed(title="予約パネル",description="クリックで予約 / 再クリックでキャンセル")
    await interaction.response.send_message(embed=embed,view=TimeView(times))

# ===== list =====
@bot.tree.command(name="list")
async def list_res(interaction:discord.Interaction):
    c.execute("SELECT time,user_id FROM schedule ORDER BY time")
    rows=c.fetchall()

    if not rows:
        await interaction.response.send_message("予約なし")
        return

    txt=""
    for t,u in rows:
        txt+=f"{t} <@{u}>\n"

    await interaction.response.send_message(embed=discord.Embed(title="予約一覧",description=txt))

# ===== reset =====
@bot.tree.command(name="reset")
async def reset(interaction:discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者のみ",ephemeral=True)
        return

    c.execute("DELETE FROM schedule")
    conn.commit()
    await interaction.response.send_message("予約全削除")

# ===== setlog =====
@bot.tree.command(name="setlog")
async def setlog(interaction:discord.Interaction,channel:discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者のみ",ephemeral=True)
        return

    c.execute("DELETE FROM config WHERE key='log'")
    c.execute("INSERT INTO config VALUES(?,?)",("log",str(channel.id)))
    conn.commit()
    await interaction.response.send_message(f"{channel.mention} をログに設定")

# ===== 通知 & 自動削除 =====
@tasks.loop(seconds=30)
async def notify():
    now=(datetime.now()+timedelta(minutes=3)).strftime("%H:%M")
    del_time=datetime.now().strftime("%H:%M")

    c.execute("SELECT time,user_id FROM schedule WHERE time=?",(now,))
    rows=c.fetchall()

    log=get_log()
    ch=bot.get_channel(log) if log else None

    for t,u in rows:
        if ch:
            await ch.send(f"<@{u}> ⏰ {t} の3分前")

    # 時間到達で削除
    c.execute("DELETE FROM schedule WHERE time=?",(del_time,))
    conn.commit()

const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, SlashCommandBuilder, PermissionFlagsBits } = require("discord.js");
const fs = require("fs");

const client = new Client({ intents: [GatewayIntentBits.Guilds] });

const TOKEN = "BOT_TOKEN";
const DATA = "./data.json";

let db = { reservations:{}, log:{} };
if (fs.existsSync(DATA)) db = JSON.parse(fs.readFileSync(DATA));

function save(){ fs.writeFileSync(DATA, JSON.stringify(db,null,2)); }

function key(guild,slot){ return guild+"_"+slot }

function schedule(guild,slot,user,channel){
  const time = new Date(slot).getTime();
  const now = Date.now();

  const before = time - now - 180000;
  if(before>0){
    setTimeout(()=>{
      channel.send(`<@${user}> 3分前通知`);
    },before);
  }

  const at = time - now;
  if(at>0){
    setTimeout(()=>{
      channel.send(`<@${user}> 時間です`);
      delete db.reservations[key(guild,slot)];
      save();
    },at);
  }
}

client.once("ready",()=>{
  console.log("ready");

  for(const k in db.reservations){
    const r = db.reservations[k];
    const ch = client.channels.cache.get(r.channel);
    if(ch) schedule(r.guild,r.slot,r.user,ch);
  }
});

client.on("interactionCreate", async i=>{
  if(i.isChatInputCommand()){

    if(i.commandName==="setlog"){
      db.log[i.guildId]=i.channelId;
      save();
      i.reply("ログ設定完了");
    }

    if(i.commandName==="re"){
      const embed=new EmbedBuilder().setTitle("予約").setDescription("押して予約");
      const row=new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId("reserve").setLabel("予約").setStyle(ButtonStyle.Primary),
        new ButtonBuilder().setCustomId("cancel").setLabel("キャンセル").setStyle(ButtonStyle.Danger)
      );
      i.channel.send({embeds:[embed],components:[row]});
      i.reply({content:"再生成完了",ephemeral:true});
    }
  }

  if(i.isButton()){
    const slot = new Date(Date.now()+600000).toISOString();
    const k = key(i.guildId,slot);

    if(i.customId==="reserve"){
      if(db.reservations[k]) return i.reply({content:"埋まってる",ephemeral:true});

      db.reservations[k]={guild:i.guildId,user:i.user.id,slot,channel:i.channelId};
      save();

      const log = db.log[i.guildId];
      if(log){
        const ch = client.channels.cache.get(log);
        if(ch) ch.send(`${i.user.tag} が予約`);
      }

      schedule(i.guildId,slot,i.user.id,i.channel);

      i.reply({content:"予約完了",ephemeral:true});
    }

    if(i.customId==="cancel"){
      if(!db.reservations[k]) return i.reply({content:"なし",ephemeral:true});
      if(db.reservations[k].user!==i.user.id) return i.reply({content:"本人のみ",ephemeral:true});

      delete db.reservations[k];
      save();

      i.reply({content:"キャンセル",ephemeral:true});
    }
  }
});

client.login(TOKEN);

client.application?.commands.set([
  new SlashCommandBuilder().setName("setlog").setDescription("ログ設定"),
  new SlashCommandBuilder().setName("re").setDescription("パネル再生成")
]);

@bot.event
async def on_ready():
    await bot.tree.sync()
    notify.start()
    print("ready")

bot.run(TOKEN)
