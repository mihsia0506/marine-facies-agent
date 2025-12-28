我是用一般 docker 指令運行的，並且在Docker裡的environment variables存有兩個金鑰
請根據env_set.txt將金鑰存進去

安裝Docker

啟動 Open WebUI
    docker run -d `
        -p 3000:8080 `
        -v open-webui:/app/backend/data `
        --name open-webui `
        ghcr.io/open-webui/open-webui:main

連線LLM API
    打開Open WebUI ->
    畫面右上角頭像 -> 
    管理員控制台 -> 
    設定 -> 
    連線 -> 
    管理 Ollama API 連線的右邊新增連線 ->
    API 基底 URL = https://api-gateway.netdb.csie.ncku.edu.tw ->
    Bearer = API KEY ->
    儲存

工具設置
    Open WebUI 畫面右方工作區 ->
    工具 ->
    新增工具 ->
    工具名稱填Sea Day ->
    工具描述 = 輸入地點時間得到海相 ->
    將Sea_Day.py貼入覆蓋下方區域 ->
    儲存

模型設置
    Open WebUI 畫面右方工作區 ->
    模型 ->
    新增模型 ->
    模型名稱 Marine Facies Agent ->
    系統提示詞請將workspace.txt的內容貼入此區 ->
    勾選工具Sea Day ->
    儲存

開始使用
    Open WebUI 畫面右方工作區 ->
    新增對話 ->
    選擇Marine Facies Agent模型
