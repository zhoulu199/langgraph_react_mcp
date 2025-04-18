## README

### 简介

本项目包含一个用于爬取美国当前新冠病毒和其他呼吸系统病原动态的Python脚本。该脚本利用web爬虫技术从CDC网站获取数据，并可与MCP集成，实现异步数据爬取。

### 特点

- **定向爬取**: 脚本专注于爬取新冠病毒和其他呼吸系统病原（如流感、RSV）的数据。
- **MCP集成**: 支持MCP调用，实现异步爬取。
- **JSON输出**: 爬取的数据以结构化JSON格式保存，方便分析。

### 环境准备

1. **安装依赖**:
   ```bash
   uv pip install requests beautifulsoup4 aiohttp mcp
   ```
2. **创建虚拟环境（推荐）**:
   ```bash
   uv venv
   uv activate
   ```
3. **设置环境变量**：
   如果使用FireCrawl，需在`.env`文件中设置`FIRECRAWL_API_KEY`和`FIRECRAWL_ENDPOINT`。

### 使用方法

#### 运行脚本

```bash
uv run epi-crawl.py
```

#### MCP集成

本脚本支持MCP Client调用，提供两个MCP工具：

1. get_us_epidata:

  - 功能: 获取美国当前的呼吸系统病原数据，包括COVID-19、流感和RSV的检测阳性率，以及COVID-19变异体比例和废水病毒活跃水平。

  - 用法: 使用MCP Client调用此工具以获取最新的美国呼吸系统病原数据。

2. crawl_2_url:

  - 功能: 异步爬取两个指定的URL，返回爬取到的HTML内容。

  - 用法: 使用MCP Client调用此工具以异步爬取多个网页，提高爬取效率。

#### 无需输入

脚本不需要任何命令行输入参数。

### 输入输出

#### 输出

- **JSON文件**: 脚本生成一个名为`data_us_.json`的文件，包含爬取的数据。JSON结构包括：
  - **all_respiratory_viruses**:
    - **summary**: 当前呼吸系统病原活动的简要总结。
    - **trends**: 历史数据，包括COVID-19、流感和RSV的检测阳性率。
  - **clinical_cov**:
    - **trends**: COVID-19的检测阳性率趋势。
    - **variants**: 当前COVID-19变异体比例。
  - **wastewater_cov**:
    - **trends**: COVID-19废水病毒活跃水平。
    - **variants**: 废水中检测到的变异体。

#### 示例输出

以下是输出JSON文件的部分示例：

```json
{
  "all_respiratory_viruses": {
    "summary": "Activity Levels Update:Reported on Friday, April 4, 2025The amount of acute respiratory illness causing people to seek health care remains at a low level.Nationally, emergency department visits for diagnosed influenza, COVID-19 and RSV are low.Nationally, influenza (9.7%), and RSV (4.1%) test positivity decreased. COVID-19 (3.7%) test positivity remained stable.Nationally, wastewater viral activity levels for influenza A and COVID-19 are low, and RSV is now very low.COVID-19 predictions for the next two weeks suggest that emergency department visits will decline from a low to very low level. Influenza predictions suggest that emergency department visits will remain at a low level.",
    "trends": [
      {
        "date": "2025-03-29",
        "COVID-19_percent_of_tests_positive": 3.7,
        "Influenza_percent_of_tests_positive": 9.7,
        "RSV_percent_of_tests_positive": 4.1
      },
      {
        "date": "2025-03-22",
        "COVID-19_percent_of_tests_positive": 3.6,
        "Influenza_percent_of_tests_positive": 10.8,
        "RSV_percent_of_tests_positive": 4.5
      }
    ]
  },
  "clinical_cov": {
    "trends": [
      {
        "date": "2025-03-29",
        "COVID-19_percent_of_tests_positive": 3.7
      },
      {
        "date": "2025-03-22",
        "COVID-19_percent_of_tests_positive": 3.6
      }
    ],
    "variants": {
      "date": "2025-03-29",
      "percentage": "LP.8.1:55%;XEC:21%;MC.10.1:4%;LF.7:4%;KP.3.1.1:3%;MC.28.1:3%;LB.1.3.1:2%;XEC.4:2%;XEQ:2%;MC.19:1%;MC.1:1%;KP.3:1%;XEK:0%;JN.1.16:0%;JN.1:0%;KP.1.1.3:0%;KP.2.3:0%"
    }
  },
  "wastewater_cov": {
    "trends": [
      {
        "date": "2025-03-29",
        "COVID-19_NWSS_wastewater_viral_activity_levels": 2.46
      },
      {
        "date": "2025-03-22",
        "COVID-19_NWSS_wastewater_viral_activity_levels": 2.64
      }
    ],
    "variants": [
      {
        "date": "2025-03-22",
        "percentage": "BA.2:N/A;BA.2.86:N/A;BA.5:N/A;BQ.1:N/A;BQ.1.1:N/A;EG.5:N/A;FL.1.5.1:N/A;HK.3:N/A;HV.1:N/A;JN.1:7%;XBB:N/A;XBB.1.16:N/A;XBB.1.16.1:N/A;XBB.1.16.6:N/A;XBB.1.5:N/A;XBB.1.5.1:N/A;XBB.1.5.59:N/A;XBB.1.9.1:N/A;XBB.1.9.2:N/A;XBB.2.3:N/A;JN.1.11.1:N/A;JN.1.7:N/A;JN.1.8.1:N/A;KP.2:N/A;KP.1.1:N/A;KP.3:8%;LB.1:N/A;KP.2.3:N/A;KP.3.1.1:N/A;XEC:15%;MC.1:N/A;MC.19:N/A;LB.1.3.1:N/A;LP.8.1:36%;XEC.4:N/A;MC.10.1:N/A;Other:35%"
      }
    ]
  }
}
```
