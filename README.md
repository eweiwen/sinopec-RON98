# sinopec-RON98 · 广东爱跑98适用油站工作台

广东地区中石化"爱跑98"会员权益（98# 直降 2 元/升，约等于与 95# 同价）仅适用于**中石化自营且销售爱跑98**的加油站。本工具把指定区域的近千座中石化站点做成可搜索、可按距离排序、可一键导航的手机端工作台，并用三态标记管理核验进度。

**线上地址**：https://eweiwen.github.io/sinopec-RON98/

## 覆盖区域

深圳（151）· 珠海（64）· 广州（260）· 惠州（181）· 东莞（135）· 汕头（49）· 肇庆（113）· 深汕特别合作区（5）

## 数据口径

| 字段 | 说明 |
|---|---|
| 底表来源 | 高德开放平台 POI，typecode=010101（中国石化），GCJ-02 坐标 |
| 状态 `confirmed` | 已核实：确认自营且销售爱跑98 |
| 状态 `unverified` | 待核实：中石化站点，自营属性与油品待确认（首版全部为此状态） |
| 状态 `unlikely` | 疑似不参与：名称含加盟/联营/特许特征 |
| 深汕特别合作区 | 高德无此区划，由汕尾市域按规则筛出（地址含"深汕特别合作区/深汕合作区"∪ 名称含"深圳" ∪ 地址含"科教大道"） |

**重要**：本工具为非官方个人工具，站点是否自营、是否销售 98# 汽油，请以"易捷加油"APP 油品展示与加油站现场为准。

## 日常维护

### 1. 更新站点数据（本机）

```bash
# key 不入库：写入本地文件或环境变量
echo <你的高德key> > scripts/.amap_key

python scripts/run_all.py   # 抓取 -> 清洗 -> 输出 data/stations.json
```

核对 `data/stations.json` 变更后提交推送，Actions 会自动重新部署。

### 2. 人工核验升级

实地确认某站后，直接编辑 `data/stations.json` 中该站的 `status` 字段为 `confirmed`（或 `unlikely`），提交即可，无需重跑抓取。

### 3. 配置地图密钥（管理员，一次性）

1. GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret
   - `AMAP_KEY`：高德开放平台 **Web端(JS API)** 类型的 Key
   - `AMAP_SECURITY_CODE`：该 Key 对应的安全密钥 jscode（未开启则不用配）
2. 建议在高德控制台为该 Key 配置域名白名单：`https://eweiwen.github.io/*`
3. 配好后于 Actions 页面手动 Run workflow（或推一个空提交），页面即带内嵌地图；
   未配置时页面自动降级为列表模式，功能不受影响。

> 注意：抓取 POI 用的是 Web服务类型 key，与页面 JS API key 平台类型不同，请勿把 Web服务 key 暴露到前端。

### 4. 启用 GitHub Pages（首次，一次性）

Settings → Pages → Build and deployment → Source 选择 **GitHub Actions**。

## 目录结构

```
index.html                    工作台页面（列表/地图/定位/搜索/导航）
data/stations.json            最终站点数据（提交入库，改数据即更新）
scripts/fetch_pois.py         高德 POI 抓取（城市级+区级双重采集）
scripts/fetch_aipao_hits.py   "爱跑98"关键词命中采集（弱证据，仅供人工复核参考）
scripts/build_stations.py     清洗/去重/深汕重分类/三态标记
scripts/run_all.py            管线入口
assets/config.js              密钥模板（Actions 构建时注入，仓库永不含真实 key）
.github/workflows/deploy.yml  Pages 部署（自动注入 Secret）
```
