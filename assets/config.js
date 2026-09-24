// ===================================================================
// 高德地图密钥模板 —— 真实值由 GitHub Actions 构建时从仓库 Secret 注入，
// 本文件在仓库中永远只保存占位符（安全设计，请勿在此填写真实 key）。
//
// 配置方法（仅仓库管理员需要做一次）：
//   GitHub 仓库 -> Settings -> Secrets and variables -> Actions
//   -> New repository secret，分别添加：
//     AMAP_KEY             高德 Web端(JS API) 平台的 Key
//     AMAP_SECURITY_CODE   该 Key 对应的安全密钥 jscode（若未开启则留空）
//
// 本地调试：复制本文件为 config.local.js 并填入真实值，
//   在 index.html 中把 config.js 的引用临时改为 config.local.js（切勿提交）。
// ===================================================================
window.__AMAP_KEY__ = "@@AMAP_KEY@@";
window.__AMAP_SECURITY_CODE__ = "@@AMAP_SECURITY_CODE@@";
