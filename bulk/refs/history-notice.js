!function () {


    var hash = getHash();
    var hashArr = hash.split('/');

    var query = getUrlParam();

    function getHash(url) {
        return decodeURIComponent(url ? url.substring(url.indexOf('#') + 1) : window.location.hash.substr(1));
    }

    var historyMarketMap = {
        bj: 'szse',
        szse: 'szse',
        szseMain: 'szse',
        szseSme: 'szse',
        szseGem: 'szse',
        sse: 'szse',
        sseMain: 'szse',
        sseKcp: 'szse',
        hke: 'hke',
        third: 'third',
        fund: 'fund',
        bond: 'bond',
        regulator: 'regulator',
        pre_disclosure: 'pre_disclosure',
        dy: 'szse'
    }
    var historyContentMap = {
        '1': 'fulltext',
        '2': 'summary',
        '3': 'relation',
        '4': 'regulator',
        '5': 'supervise',
        'important': 'fulltext',
        '1_hkeMain': 'fulltext',
        '1_hkeGem': 'fulltext',
        '1_newThree': 'fulltext',
        '1_oldThree': 'fulltext'
    }

    //内容分类
    var contentMap = {
        fulltext: '公告',
        // summary: '摘要',
        relation: '调研',
        regulator: '停复牌及监管公告',
        supervise: '持续督导',
        fulltext_child: '定期报告'
    }
    var marketTab = {
        szse: '深沪京',
        hke: '港股',
        fund: '基金',
        bond: '债券',
    }
    var contentTabByMarket = {
        szse: ['fulltext', 'relation', 'supervise'],
        sse: ['fulltext',  'relation', 'supervise'],
        hke: ['fulltext'],
        third: ['fulltext'],
        fund: ['fulltext'],
        bond: ['fulltext'],
        regulator: ['fulltext'],
        pre_disclosure: ['fulltext'],
    }

    function getKeyValueList(map) {
        var arr = [];
        for (var key in map) {
            arr.push({key: key, value: map[key]})
        }
        return arr;
    }

    //获取的内容Tab函数
    function getlistByMapData(data, map) {
        var list = [];
        data.forEach(function (item) {
            list.push({key: item, value: map[item]});
        })
        return list;
    }

    function getParams(checked) {
        return checked.map(function (item) {
            return item.key
        }).join(';')
    }

    var filterDataMap = {
        "szse": {
            "plate": [
                {"key": "sz", "value": "深市"},
                {"key": "szmb", "value": "深主板"},
                // {"key": "szzx", "value": "中小板"},
                {"key": "szcy", "value": "创业板"},
                {"key": "sh", "value": "沪市"},
                {"key": "shmb", "value": "沪主板"},
                {"key": "shkcp", "value": "科创板"},
                {"key": "bj", "value": "北交所"}
            ],
            "category": [
                {"key": "category_ndbg_szsh", "value": "年报"},
                {"key": "category_bndbg_szsh", "value": "半年报"},
                {"key": "category_yjdbg_szsh", "value": "一季报"},
                {"key": "category_sjdbg_szsh", "value": "三季报"},
                {"key": "category_yjygjxz_szsh", "value": "业绩预告"},
                {"key": "category_qyfpxzcs_szsh", "value": "权益分派"},
                {"key": "category_dshgg_szsh", "value": "董事会"},
                {"key": "category_jshgg_szsh", "value": "监事会"},
                {"key": "category_gddh_szsh", "value": "股东会"},
                {"key": "category_rcjy_szsh", "value": "日常经营"},
                {"key": "category_gszl_szsh", "value": "公司治理"},
                {"key": "category_zj_szsh", "value": "中介报告"},
                {"key": "category_sf_szsh", "value": "首发"},
                {"key": "category_zf_szsh", "value": "增发"},
                {"key": "category_gqjl_szsh", "value": "股权激励"},
                {"key": "category_pg_szsh", "value": "配股"},
                {"key": "category_jj_szsh", "value": "解禁"},
                {"key": "category_gszq_szsh", "value": "公司债"},
                {"key": "category_kzzq_szsh", "value": "可转债"},
                {"key": "category_qtrz_szsh", "value": "其他融资"},
                {"key": "category_gqbd_szsh", "value": "股权变动"},
                {"key": "category_bcgz_szsh", "value": "补充更正"},
                {"key": "category_cqdq_szsh", "value": "澄清致歉"},
                {"key": "category_fxts_szsh", "value": "风险提示"},
                {"key": "category_tbclts_szsh", "value": "特别处理和退市"},
                {"key": "category_tszlq_szsh", "value": "退市整理期"}
            ],
            "industry": [
                {"key": "农、林、牧、渔业", "value": "农、林、牧、渔业"},
                {"key": "采矿业", "value": "采矿业"},
                {"key": "制造业", "value": "制造业"},
                {"key": "电力、热力、燃气及水生产和供应业", "value": "电力、热力、燃气及水生产和供应业"},
                {"key": "建筑业", "value": "建筑业"},
                {"key": "批发和零售业", "value": "批发和零售业"},
                {"key": "交通运输、仓储和邮政业", "value": "交通运输、仓储和邮政业"},
                {"key": "住宿和餐饮业", "value": "住宿和餐饮业"},
                {"key": "信息传输、软件和信息技术服务业", "value": "信息传输、软件和信息技术服务业"},
                {"key": "金融业", "value": "金融业"},
                {"key": "房地产业", "value": "房地产业"},
                {"key": "租赁和商务服务业", "value": "租赁和商务服务业"},
                {"key": "科学研究和技术服务业", "value": "科学研究和技术服务业"},
                {"key": "水利、环境和公共设施管理业", "value": "水利、环境和公共设施管理业"},
                {"key": "居民服务、修理和其他服务业", "value": "居民服务、修理和其他服务业"},
                {"key": "教育", "value": "教育"},
                {"key": "卫生和社会工作", "value": "卫生和社会工作"},
                {"key": "文化、体育和娱乐业", "value": "文化、体育和娱乐业"},
                {"key": "综合", "value": "综合"}
            ],
            "more": "行业",
            "relation": [
                {"key": "category_mdcf_szdy", "value": "媒体采访"},
                {"key": "category_lyhd_szdy", "value": "路演活动"},
                {"key": "category_dyhd_szdy", "value": "调研活动"},
                {"key": "category_glzd_szdy", "value": "管理制度"}
            ],
            "regulator": [
                {"key": "category_ggjgjg_tfp", "value": "停复牌"},
                {"key": "category_ggjgjg_ywtz", "value": "业务通知"},
                {"key": "category_ggjgjg_ppcfgkqz", "value": "批评处罚及公开谴责"},
                {"key": "category_ggjgjg_jyfxts", "value": "交易风险提示"},
                {"key": "category_ggjgjg_qt", "value": "其他"}
            ],
            "period": [
                {"key": "category_ndbg_szsh", "value": "年报"},
                {"key": "category_bndbg_szsh", "value": "半年报"},
                {"key": "category_yjdbg_szsh", "value": "一季报"},
                {"key": "category_sjdbg_szsh", "value": "三季报"}
            ],
            "supervise": [
                {"key": "category_bjjg", "value": "保荐机构持续督导意见"},
                {"key": "category_cwgw", "value": "财务顾问持续督导意见"}
            ],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "摘要", "name": "summary"},
                {"label": "调研", "name": "relation"},
                {"label": "停复牌及监管公告", "name": "regulator"},
                {"label": "定期报告", "name": "5"},
                {"label": "持续督导", "name": "supervise"}
            ]
        },
        "bj": {
            "plate": [
                {"key": "sz", "value": "深市"},
                {"key": "szmb", "value": "深主板"},
                // {"key": "szzx", "value": "中小板"},
                {"key": "szcy", "value": "创业板"},
                {"key": "sh", "value": "沪市"},
                {"key": "shmb", "value": "沪主板"},
                {"key": "shkcp", "value": "科创板"},
                {"key": "bj", "value": "北交所"}
            ],
            "category": [
                {"key": "category_ndbg_szsh", "value": "年报"},
                {"key": "category_bndbg_szsh", "value": "半年报"},
                {"key": "category_yjdbg_szsh", "value": "一季报"},
                {"key": "category_sjdbg_szsh", "value": "三季报"},
                {"key": "category_yjygjxz_szsh", "value": "业绩预告"},
                {"key": "category_qyfpxzcs_szsh", "value": "权益分派"},
                {"key": "category_dshgg_szsh", "value": "董事会"},
                {"key": "category_jshgg_szsh", "value": "监事会"},
                {"key": "category_gddh_szsh", "value": "股东会"},
                {"key": "category_rcjy_szsh", "value": "日常经营"},
                {"key": "category_gszl_szsh", "value": "公司治理"},
                {"key": "category_zj_szsh", "value": "中介报告"},
                {"key": "category_sf_szsh", "value": "首发"},
                {"key": "category_zf_szsh", "value": "增发"},
                {"key": "category_gqjl_szsh", "value": "股权激励"},
                {"key": "category_pg_szsh", "value": "配股"},
                {"key": "category_jj_szsh", "value": "解禁"},
                {"key": "category_gszq_szsh", "value": "公司债"},
                {"key": "category_kzzq_szsh", "value": "可转债"},
                {"key": "category_qtrz_szsh", "value": "其他融资"},
                {"key": "category_gqbd_szsh", "value": "股权变动"},
                {"key": "category_bcgz_szsh", "value": "补充更正"},
                {"key": "category_cqdq_szsh", "value": "澄清致歉"},
                {"key": "category_fxts_szsh", "value": "风险提示"},
                {"key": "category_tbclts_szsh", "value": "特别处理和退市"},
                {"key": "category_tszlq_szsh", "value": "退市整理期"}
            ],
            "industry": [
                {"key": "农、林、牧、渔业", "value": "农、林、牧、渔业"},
                {"key": "采矿业", "value": "采矿业"},
                {"key": "制造业", "value": "制造业"},
                {"key": "电力、热力、燃气及水生产和供应业", "value": "电力、热力、燃气及水生产和供应业"},
                {"key": "建筑业", "value": "建筑业"},
                {"key": "批发和零售业", "value": "批发和零售业"},
                {"key": "交通运输、仓储和邮政业", "value": "交通运输、仓储和邮政业"},
                {"key": "住宿和餐饮业", "value": "住宿和餐饮业"},
                {"key": "信息传输、软件和信息技术服务业", "value": "信息传输、软件和信息技术服务业"},
                {"key": "金融业", "value": "金融业"},
                {"key": "房地产业", "value": "房地产业"},
                {"key": "租赁和商务服务业", "value": "租赁和商务服务业"},
                {"key": "科学研究和技术服务业", "value": "科学研究和技术服务业"},
                {"key": "水利、环境和公共设施管理业", "value": "水利、环境和公共设施管理业"},
                {"key": "居民服务、修理和其他服务业", "value": "居民服务、修理和其他服务业"},
                {"key": "教育", "value": "教育"},
                {"key": "卫生和社会工作", "value": "卫生和社会工作"},
                {"key": "文化、体育和娱乐业", "value": "文化、体育和娱乐业"},
                {"key": "综合", "value": "综合"}
            ],
            "more": "行业",
            "relation": [
                {"key": "category_mdcf_szdy", "value": "媒体采访"},
                {"key": "category_lyhd_szdy", "value": "路演活动"},
                {"key": "category_dyhd_szdy", "value": "调研活动"},
                {"key": "category_glzd_szdy", "value": "管理制度"}
            ],
            "regulator": [
                {"key": "category_ggjgjg_tfp", "value": "停复牌"},
                {"key": "category_ggjgjg_ywtz", "value": "业务通知"},
                {"key": "category_ggjgjg_ppcfgkqz", "value": "批评处罚及公开谴责"},
                {"key": "category_ggjgjg_jyfxts", "value": "交易风险提示"},
                {"key": "category_ggjgjg_qt", "value": "其他"}
            ],
            "period": [
                {"key": "category_ndbg_szsh", "value": "年报"},
                {"key": "category_bndbg_szsh", "value": "半年报"},
                {"key": "category_yjdbg_szsh", "value": "一季报"},
                {"key": "category_sjdbg_szsh", "value": "三季报"}
            ],
            "supervise": [
                {"key": "category_bjjg", "value": "保荐机构持续督导意见"},
                {"key": "category_cwgw", "value": "财务顾问持续督导意见"}
            ],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "摘要", "name": "summary"},
                {"label": "调研", "name": "relation"},
                {"label": "停复牌及监管公告", "name": "regulator"},
                {"label": "定期报告", "name": "5"},
                {"label": "持续督导", "name": "supervise"}
            ]
        },
        "sse": {
            "plate": [
                {"key": "sz", "value": "深市"},
                {"key": "szmb", "value": "深主板"},
                // {"key": "szzx", "value": "中小板"},
                {"key": "szcy", "value": "创业板"},
                {"key": "sh", "value": "沪市"},
                {"key": "shmb", "value": "沪主板"},
                {"key": "shkcp", "value": "科创板"}, {"key": "bj", "value": "北交所"}
            ],
            "category": [
                {"key": "category_ndbg_szsh", "value": "年报"},
                {"key": "category_bndbg_szsh", "value": "半年报"},
                {"key": "category_yjdbg_szsh", "value": "一季报"},
                {"key": "category_sjdbg_szsh", "value": "三季报"},
                {"key": "category_yjygjxz_szsh", "value": "业绩预告"},
                {"key": "category_qyfpxzcs_szsh", "value": "权益分派"},
                {"key": "category_dshgg_szsh", "value": "董事会"},
                {"key": "category_jshgg_szsh", "value": "监事会"},
                {"key": "category_gddh_szsh", "value": "股东会"},
                {"key": "category_rcjy_szsh", "value": "日常经营"},
                {"key": "category_gszl_szsh", "value": "公司治理"},
                {"key": "category_zj_szsh", "value": "中介报告"},
                {"key": "category_sf_szsh", "value": "首发"},
                {"key": "category_zf_szsh", "value": "增发"},
                {"key": "category_gqjl_szsh", "value": "股权激励"},
                {"key": "category_pg_szsh", "value": "配股"},
                {"key": "category_jj_szsh", "value": "解禁"},
                {"key": "category_gszq_szsh", "value": "公司债"},
                {"key": "category_kzzq_szsh", "value": "可转债"},
                {"key": "category_qtrz_szsh", "value": "其他融资"},
                {"key": "category_gqbd_szsh", "value": "股权变动"},
                {"key": "category_bcgz_szsh", "value": "补充更正"},
                {"key": "category_cqdq_szsh", "value": "澄清致歉"},
                {"key": "category_fxts_szsh", "value": "风险提示"},
                {"key": "category_tbclts_szsh", "value": "特别处理和退市"},
                {"key": "category_tszlq_szsh", "value": "退市整理期"}
            ],
            "industry": [
                {"key": "农、林、牧、渔业", "value": "农、林、牧、渔业"},
                {"key": "采矿业", "value": "采矿业"},
                {"key": "制造业", "value": "制造业"},
                {"key": "电力、热力、燃气及水生产和供应业", "value": "电力、热力、燃气及水生产和供应业"},
                {"key": "建筑业", "value": "建筑业"},
                {"key": "批发和零售业", "value": "批发和零售业"},
                {"key": "交通运输、仓储和邮政业", "value": "交通运输、仓储和邮政业"},
                {"key": "住宿和餐饮业", "value": "住宿和餐饮业"},
                {"key": "信息传输、软件和信息技术服务业", "value": "信息传输、软件和信息技术服务业"},
                {"key": "金融业", "value": "金融业"},
                {"key": "房地产业", "value": "房地产业"},
                {"key": "租赁和商务服务业", "value": "租赁和商务服务业"},
                {"key": "科学研究和技术服务业", "value": "科学研究和技术服务业"},
                {"key": "水利、环境和公共设施管理业", "value": "水利、环境和公共设施管理业"},
                {"key": "居民服务、修理和其他服务业", "value": "居民服务、修理和其他服务业"},
                {"key": "教育", "value": "教育"},
                {"key": "卫生和社会工作", "value": "卫生和社会工作"},
                {"key": "文化、体育和娱乐业", "value": "文化、体育和娱乐业"},
                {"key": "综合", "value": "综合"}
            ],
            "more": "行业",
            "regulator": [
                {"key": "category_ggjgjg_tfp", "value": "停复牌"},
                {"key": "category_ggjgjg_ywtz", "value": "业务通知"},
                {"key": "category_ggjgjg_ppcfgkqz", "value": "批评处罚及公开谴责"},
                {"key": "category_ggjgjg_jyfxts", "value": "交易风险提示"},
                {"key": "category_ggjgjg_qt", "value": "其他"}
            ],
            "period": [
                {"key": "category_ndbg_szsh", "value": "年报"},
                {"key": "category_bndbg_szsh", "value": "半年报"},
                {"key": "category_yjdbg_szsh", "value": "一季报"},
                {"key": "category_sjdbg_szsh", "value": "三季报"}
            ],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "摘要", "name": "summary"},
                {"label": "停复牌及监管公告", "name": "regulator"},
                {"label": "定期报告", "name": "5"}
            ]
        },
        "hke": {
            "plate": [
                {"key": "hkmb", "value": "港主板"},
                {"key": "hkcy", "value": "港创业板"}
            ],
            "category": [],
            "industry": [],
            "more": "",
            "tabList": [
                {"label": "公告", "name": "fulltext"}
            ]
        },
        "third": {
            "plate": [
                {"key": "neeq", "value": "新三板"},
                {"key": "staq", "value": "老三板"}
            ],
            "category": [
                {"key": "category_lsgg", "value": "临时公告"},
                {"key": "category_dqgg", "value": "定期公告"},
                {"key": "category_zjjg", "value": "中介机构公告"},
                {"key": "category_cxpl", "value": "持续信息披露"},
                {"key": "category_scpl", "value": "首次信息披露"}
            ],
            "industry": [
                {"key": "农、林、牧、渔业", "value": "农、林、牧、渔业"},
                {"key": "采矿业", "value": "采矿业"},
                {"key": "制造业", "value": "制造业"},
                {"key": "电力、热力、燃气及水生产和供应业", "value": "电力、热力、燃气及水生产和供应业"},
                {"key": "建筑业", "value": "建筑业"},
                {"key": "批发和零售业", "value": "批发和零售业"},
                {"key": "交通运输、仓储和邮政业", "value": "交通运输、仓储和邮政业"},
                {"key": "住宿和餐饮业", "value": "住宿和餐饮业"},
                {"key": "信息传输、软件和信息技术服务业", "value": "信息传输、软件和信息技术服务业"},
                {"key": "金融业", "value": "金融业"},
                {"key": "房地产业", "value": "房地产业"},
                {"key": "租赁和商务服务业", "value": "租赁和商务服务业"},
                {"key": "科学研究和技术服务业", "value": "科学研究和技术服务业"},
                {"key": "水利、环境和公共设施管理业", "value": "水利、环境和公共设施管理业"},
                {"key": "居民服务、修理和其他服务业", "value": "居民服务、修理和其他服务业"},
                {"key": "教育", "value": "教育"},
                {"key": "卫生和社会工作", "value": "卫生和社会工作"},
                {"key": "文化、体育和娱乐业", "value": "文化、体育和娱乐业"},
                {"key": "综合", "value": "综合"}
            ]
        },
        "neeq": {
            "category": [
                {"key": "category_lsgg", "value": "临时公告"},
                {"key": "category_dqgg", "value": "定期公告"},
                {"key": "category_zjjg", "value": "中介机构公告"},
                {"key": "category_cxpl", "value": "持续信息披露"},
                {"key": "category_scpl", "value": "首次信息披露"}
            ],
            "more": "行业",
            "period": [],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "定期报告", "name": "5"}
            ]
        },
        "staq": {
            "category": [
                {"key": "category_lsgg", "value": "临时公告"},
                {"key": "category_dqgg", "value": "定期公告"},
                {"key": "category_zjjg", "value": "中介机构公告"},
                {"key": "category_cxpl", "value": "持续信息披露"},
                {"key": "category_scpl", "value": "首次信息披露"}
            ],
            "more": "行业",
            "period": [],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "定期报告", "name": "5"}
            ]
        },
        "fund": {
            "category": [
                {"key": "category_jjzm_jjgg", "value": "招募设立"},
                {"key": "category_smsgx_jjgg", "value": "说明书更新"},
                {"key": "category_ndbg_jjgg", "value": "年报"},
                {"key": "category_bndbg_jjgg", "value": "中报"},
                {"key": "category_jdbg_jjgg", "value": "季报"},
                {"key": "category_jzgg_jjgg", "value": "净值"},
                {"key": "category_zhtz_jjgg", "value": "投资组合"},
                {"key": "category_sgsh_jjgg", "value": "申购赎回"},
                {"key": "category_jjfl_jjgg", "value": "基金费率"},
                {"key": "category_xsqd_jjgg", "value": "销售渠道"},
                {"key": "category_fh_jjgg", "value": "分红"},
                {"key": "category_ggjjjl_jjgg", "value": "高管及基金经理"},
                {"key": "category_fecyr_jjgg", "value": "持有人大会"},
                {"key": "category_jbxxbg_jjgg", "value": "基本信息变更"},
                {"key": "category_ndbg_jjgg;category_bndbg_jjgg;category_jdbg_jjgg", "value": "定期报告"},
                {"key": "category_qt_jjgg", "value": "其他"}
            ],
            "industry": [],
            "more": "",
            "regulator": [
                {"key": "category_ggjgjg_tfp", "value": "停复牌"},
                {"key": "category_ggjgjg_ywtz", "value": "业务通知"},
                {"key": "category_ggjgjg_ppcfgkqz", "value": "批评处罚及公开谴责"},
                {"key": "category_ggjgjg_jyfxts", "value": "交易风险提示"},
                {"key": "category_ggjgjg_qt", "value": "其他"}
            ],
            "period": [
                {"key": "category_ndbg_jjgg", "value": "年报"},
                {"key": "category_bndbg_jjgg", "value": "中报"},
                {"key": "category_jdbg_jjgg", "value": "季报"}
            ],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "停复牌及监管公告", "name": "regulator"},
                {"label": "定期报告", "name": "5"}
            ]
        },
        "bond": {
            "category": [
                {"key": "category_zqfxss_zqgg", "value": "债券发行上市"},
                {"key": "category_zqdq_zqgg", "value": "债券定期公告"},
                {"key": "category_zqfx_zqgg", "value": "债券付息公告"},
                {"key": "category_zqdqdftz_zqgg", "value": "债券到期兑付停止交易公告"},
                {"key": "category_zqqt_zqgg", "value": "债券其他公告"}
            ],
            "more": "",
            "regulator": [
                {"key": "category_ggjgjg_tfp", "value": "停复牌"},
                {"key": "category_ggjgjg_ywtz", "value": "业务通知"},
                {"key": "category_ggjgjg_ppcfgkqz", "value": "批评处罚及公开谴责"},
                {"key": "category_ggjgjg_jyfxts", "value": "交易风险提示"},
                {"key": "category_ggjgjg_qt", "value": "其他"}
            ],
            "period": [],
            "tabList": [
                {"label": "公告", "name": "fulltext"},
                {"label": "停复牌及监管公告", "name": "regulator"},
                {"label": "定期报告", "name": "5"}
            ]
        },
        "regulator": {
            "org": [
                {"key": "jgjg_sz", "value": "深交所"},
                {"key": "jgjg_sh", "value": "上交所"},
                {"key": "jgjg_jsgs", "value": "结算公司"},
                {"key": "jgjg_zjh", "value": "证监会"},
                {"key": "jgjg_bj", "value": "北交所"},
            ],
            "category": [
                {"key": "category_jgjg_tfp", "value": "停复牌"},
                {"key": "category_jgjg_ywtz", "value": "业务通知"},
                {"key": "category_jgjg_ppcfgkqz", "value": "批评处罚及公开谴责"},
                {"key": "category_jgjg_jyfxts", "value": "交易风险提示"},
                {"key": "category_jgjg_qt", "value": "其他"}
            ]
        },
        "pre_disclosure": {
            "more": "",
            "category": ""
        },
    }
    var main = new Vue({
        el: '#main',
        data: function () {
            return {
                actMarket: hashArr[0] ? historyMarketMap[hashArr[0]] : 'szse',
                actContent: hashArr[1] ? historyContentMap[hashArr[1]] : 'fulltext',
                marketTabList: getKeyValueList(marketTab),
                fundList: [
                    {key: 'ABCDE', value: []},
                    {key: 'FGHJ', value: []},
                    {key: 'KLMNOP', value: []},
                    {key: 'QRSTW', value: []},
                    {key: 'XYZ', value: []}
                ],
                titleKeyword: '',
                actFundLetter: 'ABCDE',
                filterDataMap: filterDataMap,
                //页码信息
                page: {
                    num: 1,
                    size: 30,
                    total: 0
                },
                closeToal: '',
                //选中条件
                checkedCategory: [],
                checkedPlate: [],
                checkedIndustry: [],
                checkedPlace: [],
                checkedOrg: [],
                checkedStocks: [],
                checkedSearchKeys: [],
                checkedFund: [],
                //查询参数
                sortName: '',
                sortType: '',
                keyWords: '',
                date: [],
                // pickerOption: pickerOption,
                //渲染数据层面
                hotTag: [], //热门搜索
                dataList: [],//公告列表
                dataList2: [],
                loading: false,
                quickSortList: [],
                stockList: [], //键盘精灵
                selectStockList: [],
                total: 0,
                clickDate: '',
                //右侧下方广告图
                nxtADPic: {},
                limitTime: (3 * 365 + 1) * 24 * 3600 * 1000,
                isIE9: navigator.appName == 'Microsoft Internet Explorer' && navigator.appVersion.match(/9./i) == '9.',
                tagFlag: false,
            }
        },
        computed: {
            lastPageNone: function () {
                return this.page.total < 600 ? false :
                    Math.ceil(this.page.total / this.page.size) - this.page.num < 3 ? false : true;
            },
            pickerOption: function () {
                var _this = this;
                return {
                    disabledDate: function (time) {
                        return time.getTime() < new Date("1999-12-31")
                    },
                    shortcuts: [{
                        text: '明日',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            end.setTime(start.getTime() + 3600 * 1000 * 24 * 1);
                            picker.$emit('pick', [end, end]);
                        }
                    }, {
                        text: '今日',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            picker.$emit('pick', [start, end]);
                        }
                    }, {
                        text: '近1周',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
                            if (end.getHours() >= 15) {
                                end.setTime(end.getTime() + 3600 * 1000 * 24);
                            }
                            picker.$emit('pick', [start, end]);
                        }
                    }, {
                        text: '近1月',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            start.setTime(start.getTime() - 3600 * 1000 * 24 * 30);
                            if (end.getHours() >= 15) {
                                end.setTime(end.getTime() + 3600 * 1000 * 24);
                            }
                            picker.$emit('pick', [start, end]);
                        }
                    }, {
                        text: '近3月',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            start.setTime(start.getTime() - 3600 * 1000 * 24 * 90);
                            if (end.getHours() >= 15) {
                                end.setTime(end.getTime() + 3600 * 1000 * 24);
                            }
                            picker.$emit('pick', [start, end]);
                        }
                    }, {
                        text: '近6月',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            start.setTime(start.getTime() - 3600 * 1000 * 24 * 180);
                            if (end.getHours() >= 15) {
                                end.setTime(end.getTime() + 3600 * 1000 * 24);
                            }
                            picker.$emit('pick', [start, end]);
                        }
                    }, {
                        text: '近1年',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            start.setTime(start.getTime() - 3600 * 1000 * 24 * 365);
                            if (end.getHours() >= 15) {
                                end.setTime(end.getTime() + 3600 * 1000 * 24);
                            }
                            picker.$emit('pick', [start, end]);
                        }
                    }, {
                        text: '近3年',
                        onClick: function (picker) {
                            var end = new Date();
                            var start = new Date();
                            start.setTime(start.getTime() - 3600 * 1000 * 24 * 365 * 3);
                            if (end.getHours() >= 15) {
                                end.setTime(end.getTime() + 3600 * 1000 * 24);
                            }
                            picker.$emit('pick', [start, end]);
                        }
                    }]
                }
            },
            conditionVisible: function () {
                return [].concat(this.checkedPlate, this.checkedCategory, this.checkedIndustry, this.checkedSearchKeys, this.checkedFund, this.checkedOrg, this.checkedStocks, this.checkedPlace).length == 0 ? false : true;
            },
            //基金 债券 监管 预披露 与其他版块显示不一样
            specialAnnounce: function () {
                return ['fund', 'bond', 'regulator', 'pre_disclosure'].indexOf(this.actMarket) > -1 ? true : false;
            },
            specialSummary: function () {
                return ['regulator', 'pre_disclosure'].indexOf(this.actMarket) > -1 ? true : false;
            },
            placeholder: function () {
                return this.specialSummary ? '标题关键字' : '代码/简称/拼音';
            },
            stockPlate: function () {
                return {
                    szse: 'szsh',
                    hke: 'hke',
                    third: 'staqneeq',
                    fund: 'fund',
                    bond: 'bond'
                }[this.actMarket]
            },

            //内容tab
            contentTabList: function () {
                return getlistByMapData(contentTabByMarket[this.actMarket], contentMap);
            },
            //板块筛选
            plateList: function () {
                //如为调研，板块只展示深市
                var list = this.tabName != 'relation' ? filterDataMap[this.actMarket].plate:filterDataMap[this.actMarket].plate.slice(0,3)
                return list ? list : [];
            },
            //分类筛选
            categoryList: function () {
                if (this.actContent == 'relation') {
                    // return filterDataMap[this.actMarket].relation;
                    return [];

                } else if (this.actContent == 'supervise') {
                    return filterDataMap[this.actMarket].supervise;
                } else if (this.actContent == 'fulltext_child') {
                    return filterDataMap[this.actMarket].period;
                } else {
                    var list = filterDataMap[this.actMarket].category
                    if(list){
                        if(this.actMarket != 'dy'&&this.actMarket != 'hke'&&this.actMarket != 'bond'&&this.actMarket != 'third'&&this.actMarket != 'regulator'&&!this.tagFlag){
                            list = list.slice(0,12)
                        }
                        return list
                    }else{
                        return []
                    }
                    // return list ? list : [];
                }

            },
            categoryListStock: function () {
                if (this.actContent == 'relation') {
                    // return filterDataMap[this.actMarket].relation;
                    return [];

                } else if (this.actContent == 'supervise') {
                    return filterDataMap[this.actMarket].supervise;
                } else if (this.actContent == 'fulltext_child') {
                    return filterDataMap[this.actMarket].period;
                } else {
                    var list = filterDataMap[this.actMarket].category
                    return list ? list : [];
                }

            },
            //行业筛选
            industryList: function () {
                var list = filterDataMap[this.actMarket].industry
                return list ? list : [];
            },
            //上市地筛选
            placeList: function () {
                var list = filterDataMap[this.actMarket].place
                return list ? list : [];
            },
            //机构筛选
            orgList: function () {
                var list = filterDataMap[this.actMarket].org
                return list ? list : [];
            },
            //获取json url字段
            stockStr: function () {
                return {
                    szse: 'szse_stock',
                    hke: 'hke_stock',
                    third: 'gfzr_stock',
                    fund: 'fund_stock',
                    bond: 'bond_stock',
                    regulator: '',
                    pre_disclosure: ''
                }[this.actMarket]
            },
            //------请求接口参数-----------
            column: function () {
                return this.actMarket;
            },
            tabName: function () {
                var tabName = '';
                switch (this.actContent) {
                    case 'fulltext_child':
                        tabName = 'fulltext';
                        break;
                    default:
                        tabName = this.actContent;
                }

                return tabName;
            },
            plate: function () {
                if (this.actMarket == 'regulator') {
                    return getParams(this.checkedOrg);
                } else if (this.actMarket == 'bond') {
                    return getParams(this.checkedPlace);
                } else {
                    return getParams(this.checkedPlate);
                }
            },
            category: function () {
                return getParams(this.checkedCategory);
            },
            industry: function () {
                return getParams(this.checkedIndustry);
            },
            stock: function () {
                return this.checkedStocks.map(function (item) {
                    return item.code + ',' + item.orgId;
                }).join(';')
            },
            searchkey: function () {
                return this.checkedSearchKeys.join(';');
            },
            secid: function () {
                return this.checkedFund.map(function (item) {
                    return item.companyId
                }).join(';');
            },
            seDate: function () {
                var date = this.date;
                return date ? (date[0] + '~' + date[1]) : '';
            },
            //判断当前市场栏目tab是否有当前内容tab
            hasContentTab: function () {
                var _this = this;
                return this.contentTabList.filter(function (item) {
                    return item.key == _this.actContent;
                }).length > 0 ? true : false;
            },
        },
        methods: {
            checkChangeFlag: function(){
                this.tagFlag = !this.tagFlag
            },
            getCodeListByAid: function (item) {
                var _this = this;
                axios({
                    url: path + '/hisAnnouncement/getSecnameByAnnouncementId',
                    method: 'post',
                    params: {
                        announcementId: item.announcementId
                    }
                }).then(function (res) {
                    item.fundsList = res;
                })
            },
            rowClassCb: function (cell) {
                if (this.actMarket == 'fund' && cell.row.secCode && cell.row.secCode.split(',').length > 1) {
                    return ''
                } else {
                    return 'hidden-expand-icon'
                }
            },
            expandRowChange: function (row, expandedRows) {
                var _this = this;
                row.showFunds = !row.showFunds
                if (row.showFunds && row.fundsList.length == 0) {
                    this.getCodeListByAid(row)
                }
            },
            quickCategory: function (key) {
                $('html,body').animate({scrollTop: 230}, 350)

                if (key == 'supervise') {
                    this.actContent = key;
                    this.checkedCategory = [];
                } else if (key == 'dingqibaogao') {
                    var dqCategory = [
                        {"key": "category_ndbg_jjgg", "value": "年报"},
                        {"key": "category_bndbg_jjgg", "value": "中报"},
                        {"key": "category_jdbg_jjgg", "value": "季报"}
                    ];
                    this.checkedCategory = this.categoryList.filter(function (item) {
                        return dqCategory.filter(function (item2) {
                            return item.key == item2.key;
                        }).length > 0 ? true : false
                    })
                } else {
                    this.actContent = 'fulltext';
                    this.checkedCategory = this.categoryList.filter(function (item) {
                        return item.key == key;
                    })
                }

                this.getHistory();
            },
            getAdPic: function () {
                // 日历下方的轮播图
                var _this = this;
                axios({
                    url: path + '/index/getPictureByColumnMark?columnMark=nxtADPic',
                    method: 'get'
                }).then(function (res) {
                    _this.nxtADPic = res.nxtADPic[0] ? res.nxtADPic[0] : {};
                })
            },
            getQuickSortList: function () {
                var _this = this;
                axios({
                    url: path + '/index/getAnnoucementType',
                    method: 'get'
                }).then(function (res) {
                    _this.quickSortList = res;
                })
            },
            //兼容ie placeholder
            iePlaceHolder: function () {
            },
            inputMouseOver: function () {
                this.$refs.autocomplete.focus();
            },
            //文件跳转
            linkLastPage: function (item) {
                var url = '';
                if (item.adjunctType == 'PPT' || item.adjunctType == 'PPTX' ||
                    item.adjunctType == "XLS" || item.adjunctType == "XLSX" ||
                    item.adjunctType == "CSV" || item.adjunctType == "PNG" ||
                    item.adjunctType == "DOC" || item.adjunctType == "DOCX") {
                    url = officeUrl + encodeURIComponent(v3_cninfo + '/' + item.adjunctUrl);

                } else {
                    if (this.actMarket == 'fund') {
                        var secCode = item.secCode ? item.secCode.split(',')[0] : '';
                    } else {
                        var secCode = item.secCode ? item.secCode : ''
                    }
                    url = path + '/disclosure/detail?stockCode=' + secCode +
                        '&announcementId=' + (item.announcementId ? item.announcementId : '') +
                        '&orgId=' + (item.orgId ? item.orgId : '') +
                        '&announcementTime=' + fomatDate(item.announcementTime, 'yyyy-MM-dd')
                }
                return url
            },
            /*keywordHeightLight: function (str) {
                var keys = this.checkedSearchKeys,
                    len = keys.length;
                for (var i = 0; i < len; i++) {
                    str = str.replace(RegExp(keys[i], "g"), '<span class="higlight">' + keys[i] + '</span>');
                }
                return str;
            },*/
            goToSearch: function () {
                var _this = this;

            },
            //搜索框
            enterQuery: function () {
                var _this = this;
                var titleKeyword = this.titleKeyword;
                var re = /select|update|delete|exec|count|……|，|\*|——|【|】|[|]|{|}|、|“|”|《|》|。|‘|’|'|"|=|~|!|\+|\(|\)|\\|\/|\?|\$|;|>|<|:|：|\^|&|@|#|%/i;

                if (re.test(titleKeyword)) {
                    alert("存在非法字符，请重新输入");
                    this.titleKeyword = '';
                    return;
                }

                var hasKeyWords = this.checkedSearchKeys.filter(function (val) {
                    return val == _this.titleKeyword;
                }).length > 0 ? true : false;

                if (!hasKeyWords && this.titleKeyword) {
                    this.checkedSearchKeys.push(this.titleKeyword);
                    this.titleKeyword = '';
                    // this.initPage();
                    // this.getHistory();
                } else {
                    this.titleKeyword = '';
                }

                if (this.selectStockList.length == 1) {
                    var hasStocks = this.checkedStocks.filter(function (val) {
                        return val.code == _this.selectStockList[0].code
                    }).length > 0 ? true : false;
                    if (!hasStocks) {
                        this.checkedStocks.push(this.selectStockList[0]);
                        this.keyWords = ''
                    }
                    // this.checkedStocks = [this.selectStockList[0]];
                }
                this.selectStockList = [];
                this.initPage();
                this.getHistory();
            },
            inputKeyword: function(){
                // this.sortName = 'score';
                // this.sortType = 'desc';
            },
            //获取code查询
            getStockList: function (callback) {
                var _this = this;
                if (_this.stockStr) {
                    $.ajax({
                        url: path + '/data/' + _this.stockStr + '.json',
                        type: 'get',
                        success: function (res) {
                            _this.stockList = res.stockList;
                        }
                    })
                } else {
                    _this.stockList = [];
                }

            },
            stockSearch: function (queryString, cb) {
                var _this = this;
                this.selectStockList = [];
                if (!_this.specialSummary && !!queryString) {
                    this.selectStockList = [];
                    // 判断是否以输入值开头
                    // if (this.keyWords == "^" || this.keyWords == "|" || this.keyWords == "*") {
                    //     this.keyWords = "\\" + this.keyWords;
                    // }
                    var count = 0;
                    for (var i = 0, len = this.stockList.length; i < len; i++) {
                        if (count >= 10) {
                            break;
                        }
                        var reg = new RegExp(this.keyWords, "ig");
                        var item = this.stockList[i];
                        if (reg.test(item.code) || reg.test(item.pinyin) || reg.test(item.zwjc)) {
                            count++;
                            this.selectStockList.push(item);
                        }
                    }
                    cb(this.selectStockList);
                } else {
                    cb([]);
                }

            },
            //键盘精灵查询
            querySearch: function (queryString, cb) {
                var _this = this;
                //监管预披露不需要键盘精灵
                if (!_this.specialSummary && queryString) {
                    $.ajax({
                        url: path + '/information/topSearch/query',
                        type: 'post',
                        data: {
                            keyWord: _this.keyWords,
                            maxNum: 10,
                            plate: _this.stockPlate
                        },
                        success: function (res) {
                            if (res) {
                                _this.selectStockList = res;
                                cb(res);

                            } else {
                                _this.selectStockList = [];
                                cb([]);
                            }
                        },
                        error: function () {
                            cb([]);
                        }
                    })
                } else {
                    cb([]);
                }

            },
            mousedownChange: function (e) {
                var _this = this;
                //解决ie9 清空赋值问题
                setTimeout(function () {
                    _this.keyWords = e.target.value;
                }, 300)
            },
            keydownChange: function (e) {
                //解决ie9 删除 回退键赋值问题
                this.keyWords = e.target.value;
            },
            handleSelect: function (item) {
                if (!item.code) {
                    return;
                }
                var hasStocks = this.checkedStocks.filter(function (val) {
                    return val.code == item.code
                }).length > 0 ? true : false;
                if (!hasStocks) {
                    this.checkedStocks.push(item);
                    this.keyWords = ''
                }
                this.initPage();
                this.getHistory();
            },
            //时间框
            dateChange: function (onlyDataChange) {
                if (this.date && this.date[0] && this.date[1]) {
                    var spaceTime = new Date(this.date[1]).getTime() - new Date(this.date[0]).getTime(),
                        hasValue = this.checkedSearchKeys.length > 0 || this.checkedStocks.length > 0;

                    if (!hasValue && spaceTime > this.limitTime) {
                        this.$msgbox({
                            type: 'warning',
                            title: '提示',
                            message: '当前查询只提供日期间隔不超过三年的数据，请增加指定股票代码或关键字。',
                        })
                        var end = new Date();
                        var start = new Date();
                        start.setTime(start.getTime() - 3600 * 1000 * 24 * 365 * 3);
                        if (end.getHours() >= 15) {
                            end.setTime(end.getTime() + 3600 * 1000 * 24);
                        }
                        this.date = [fomatDate(start, 'yyyy-MM-dd'), fomatDate(end, 'yyyy-MM-dd')];
                        return;
                    }
                }
                if (onlyDataChange) return;
                this.initPage();
                this.getHistory();

            },
            dateFocus: function () {
                this.clickDate = '';
            },

            //默认时间
            defaultDay: function () {
                var m = 6;  //后推6个月
                var date = new Date();
                var year = date.getFullYear();
                var month = date.getMonth() + 1;
                var day = date.getDate();
                var lowDate = '';
                var yearLow = parseInt(parseInt(m) / 12);
                var monthLow = parseInt(m) % 12;
                if (yearLow > 0) {
                    year = yearLow
                } else {
                    year = year;
                }
                if ((monthLow > month) || (monthLow == month)) {
                    year = year - 1;
                    month = 12 - monthLow + month;
                    lowDate = year + '-' + month + '-' + day
                } else {
                    month -= monthLow;
                    lowDate = year + '-' + month + '-' + day
                }

                if (date.getHours() >= 15) {   /*当前时间15:00以后，往后推一天*/
                    date = date.getTime() + 3600 * 1000 * 24;
                }
                lowDate = lowDate.replace(/\b\d\b/g, '0$&');
                this.defaultTime = [lowDate, fomatDate(date, 'yyyy-MM-dd')];
                this.date = this.defaultTime;
            },
            //初始化选中条件
            initCondition: function () {
                this.checkedPlate = [];
                this.checkedCategory = [];
                this.checkedIndustry = [];
                this.checkedOrg = [];
                this.checkedPlace = [];
                this.checkedStocks = [];
                this.checkedSearchKeys = [];
                this.checkedFund = [];
                this.keyWords = '';
                this.titleKeyword = '';
                this.defaultDay();
                this.$refs['notice-table'].clearSort();
                this.sortType = '';
                this.sortName = '';
            },
            //初始化页面信息
            initPage: function () {
                this.page.num = 1;
                this.page.total = 0;
            },
            //市场栏目tab切换
            switchMarket: function () {
                //如果当前市场栏目tab含有当前内容tab 没有则默认为第一个内容tab
                this.actContent = this.hasContentTab ? this.actContent : this.contentTabList[0].key;
                // $('.scroll-hd .tabs-list li[data-id=' + this.actMarket + ']').addClass('active').siblings().removeClass('active');
                this.initCondition();
                this.initPage();
                this.getHistory();
                if (this.$refs.autocomplete) {
                    this.$refs.autocomplete.suggestions = [];
                }
                this.getStockList();

            },
            //内容tab切换
            switchContent: function () {
                this.checkedPlate = [];
                this.checkCondition('checkedCategory', 'categoryList');
                this.initPage();
                this.getHistory();
            },
            checkCondition: function (checkedStr, strList) {
                var _this = this;
                var condition = this[checkedStr].slice(0);
                this[checkedStr] = condition.filter(function (item) {
                    return _this[strList].filter(function (item2) {
                        return item2.key == item.key;
                    }).length > 0 ? true : false;
                })
            },

            clearAll: function () {
                this.initCondition();
                this.initPage();
                this.getHistory();
            },
            sortChange: function (sort) {
                if (sort.prop) {
                    this.sortName = {
                        secCode: 'code',
                        announcementTitle: 'title',
                        announcementTime: 'time',
                    }[sort.prop];
                    this.sortType = {
                        ascending: 'asc',
                        descending: 'desc'
                    }[sort.order];

                } else {
                    this.sortName = '';
                    this.sortType = '';
                }
                this.page.num = 1;
                this.getHistory();
            },
            checkChange: function (item, checkedStr) {
                var _this = this
                if(checkedStr=='checkedCategory'){
                    var a = ''
                    if(this.checkedCategory.length>0){
                        if(this.checkedCategory[0].key==item.key){
                            this.checkedCategory.splice(0, 1);
                        }else{
                            this.checkedCategory.forEach(function(fItem,fIndex){
                                if(fItem.key == item.key){
                                    a = fIndex
                                }
                            })
                            if(a!=''){
                                this.checkedCategory.splice(a, 1);
                            }else{
                                this.checkedCategory.push(item)
                            }
                        }
                    }else{
                        this.checkedCategory.push(item)
                    }
                }
                this.initPage();
                this.getHistory();
            },
            //关闭条件
            closeTag: function (index, checkedStr) {
                this[checkedStr].splice(index, 1);
                // if(!this.searchkey){
                //     this.sortType = '';
                //     this.sortName = '';
                // }
                if (this.date && this.date[0] && this.date[1]) {
                    var spaceTime = new Date(this.date[1]).getTime() - new Date(this.date[0]).getTime(),
                        hasValue = this.checkedSearchKeys.length > 0 || this.checkedStocks.length > 0;
                    if (!hasValue && spaceTime > this.limitTime) {
                        this.defaultDay();
                    }
                }

                this.initPage();
                this.getHistory();
            },
            filterHTMLTag: function (msg) {
                if(!msg){
                    return ""
                }
                var msg = msg.replace(/<\/?[^>]*>/g, ''); //去除HTML Tag
                msg = msg.replace(/[|]*\n/, '') //去除行尾空格
                msg = msg.replace(/&npsp;/ig, ''); //去掉npsp
                return msg;
            },
            //判断文件格式
            checkDocType: function (type) {
                return {
                    "DOC": 'iconnotice-DOC1',
                    "DOCX": 'iconnotice-DOC1',
                    "TXT": '',
                    "PDF": 'iconnotice-PDF1',
                    "PPT": 'iconnotice-PPT1',
                    "PPTX": 'iconnotice-PPT1',
                    "XLS": 'iconnotice-EXL1',
                    "XLSX": 'iconnotice-EXL1',
                    "CSV": 'iconnotice-CSV1',
                    "JPG": 'iconnotice-JPG1',
                    "GIF": 'iconnotice-GIF1',
                    "PNG": 'iconnotice-PNG1',
                }[type]
            },
            //获取热门搜索
            getHot: function () {
                var _this = this;
                $.ajax({
                    url: path + "/fulltextSearch/hotwordspage",
                    type: 'POST',
                    success: function (res) {
                        _this.hotTag = res;
                    }
                })
            },

            //获取历史公告
            getHistory: function (beforeCb) {
                var _this = this;
                _this.loading = true;
                if (beforeCb) beforeCb();
                _this.$nextTick(function () {
                    $.ajax({
                        url: path + '/hisAnnouncement/query',
                        type: 'POST',
                        data: {
                            pageNum: _this.page.num,
                            pageSize: _this.page.size,
                            column: _this.column,
                            tabName: _this.tabName,
                            plate: _this.plate,
                            stock: _this.stock,
                            searchkey: _this.searchkey,
                            secid: _this.secid,
                            category: _this.category,
                            trade: _this.industry,
                            seDate: _this.seDate,
                            sortName: _this.sortName,
                            sortType: _this.sortType,
                            isHLtitle: true
                        },
                        success: function (res) {
                            _this.loading = false;
                            if (res && res.announcements) {
                                res.announcements.forEach(function(item){
                                    item.secName =item.secName? _this.filterHTMLTag(item.secName):item.secName
                                })
                                if (_this.specialAnnounce) {
                                    if (_this.actMarket == 'fund') {
                                        res.announcements.map(function (item) {
                                            item.showFunds = false;
                                            item.fundsList = [];
                                            return item;
                                        })
                                    }
                                    _this.dataList2 = res.announcements ? res.announcements : [];
                                } else {

                                    _this.dataList = res.announcements ? res.announcements : [];

                                }
                                _this.total = res.totalAnnouncement ? res.totalAnnouncement : 0;
                                _this.page.total = res.totalRecordNum > _this.page.size * 100 ? _this.page.size * 100 : res.totalRecordNum;
                                _this.closeToal = res.totalAnnouncement < 10000 ? '共 ' + res.totalAnnouncement + ' 条' : '约 ' + Math.floor(res.totalAnnouncement / 1000) * 1000 + ' 条';

                            } else {
                                _this.dataList = [];
                                _this.dataList2 = [];
                                _this.page.total = 0
                                _this.closeToal = "";
                            }
                        },
                        error: function (e) {
                            _this.dataList == []
                            _this.page.total = 0
                            _this.closeToal = "";
                            _this.loading = false;
                        }
                    })
                })

            },
            //获取基金公司
            getFundCompany: function () {
                var _this = this;
                $.ajax({
                    url: path + "/newInterface/getFundCompany",
                    type: 'get',
                    success: function (res) {
                        if (res) {
                            _this.fundList.forEach(function (item) {
                                item.value = res[item.key]
                            })
                        }
                    }
                })
            },
            //翻页
            changePage: function (num) {
                this.page.num = num;
                this.getHistory();
            },
            initKeyWords: function () {
                if (query.keywords) {
                    this.checkedPlate = query.keywords == query.name ? [] : this.checkedPlate;
                    this.checkedSearchKeys.push(query.keywords);
                } else {
                    this.checkedSearchKeys = [];
                }
            },
            initStocks: function () {
                if (query.code && query.orgId && query.name) {
                    //当跳转为选中某只代码公司时， 不需要携带板块， 需在initPlate 后面
                    this.checkedPlate = [];
                    this.checkedStocks.push({code: query.code, orgId: query.orgId, zwjc: query.name})
                } else {
                    this.checkedStocks = []
                }
            },
            //判断是否为定期报告跳转
            initBulletin: function () {
                if (query.bulletin) {
                    var bulletinCategory = {
                        szse: [
                            {"key": "category_ndbg_szsh", "value": "年报"},
                            {"key": "category_bndbg_szsh", "value": "半年报"},
                            {"key": "category_yjdbg_szsh", "value": "一季报"},
                            {"key": "category_sjdbg_szsh", "value": "三季报"}
                        ],
                        hke: [],
                        third: [{"key": "category_dqgg", "value": "定期公告"}],
                        fund: [
                            {"key": "category_ndbg_jjgg", "value": "年报"},
                            {"key": "category_bndbg_jjgg", "value": "中报"},
                            {"key": "category_jdbg_jjgg", "value": "季报"}
                        ],
                        bond: [
                            {"key": "category_zqdq_zqgg", "value": "债券定期公告"}
                        ],
                        regulator: [],
                        pre_disclosure: [],
                    }[this.actMarket];
                    bulletinCategory = bulletinCategory ? bulletinCategory : [];
                    this.actContent = 'fulltext';
                    this.checkedCategory = this.categoryList.filter(function (item) {
                        return bulletinCategory.filter(function (item2) {
                            return item.key == item2.key
                        }).length > 0 ? true : false;
                    })
                }

            },
            initDate: function () {

                if (query.startDate && query.endDate) {
                    var spaceTime = new Date(query.endDate).getTime() - new Date(query.startDate).getTime()

                    if (spaceTime < 0 || spaceTime > this.limitTime) {
                        this.defaultDay();
                    } else {
                        this.date = [query.startDate, query.endDate];
                    }
                } else {
                    this.defaultDay();
                }
            },
            initCheckedStr: function (checkedStr, strList) {
                if (query[checkedStr]) {
                    this[checkedStr] = this[strList].filter(function (item) {
                        return item.key == query[checkedStr]
                    })
                }
            },
            initPlate: function () {
                var plateMap = {
                    szse: 'sz',
                    bj: 'bj',
                    szseMain: 'szmb',
                    szseSme: 'szzx',
                    szseGem: 'szcy',
                    sse: 'sh',
                    sseMain: 'shmb',
                    sseKcp: 'shkcp',
                    '1_hkeMain': 'hkmb',
                    '1_hkeGem': 'hkcy',
                    '1_newThree': 'neeq',
                    '1_oldThree': 'staq'
                }
                var plateKey = plateMap[hashArr[0]] ? plateMap[hashArr[0]] : plateMap[hashArr[1]];
                if (plateKey && hashArr[1] != 2) {
                    this.checkedPlate = this.plateList.filter(function (item) {
                        return item.key == plateKey;
                    })
                } else {
                    this.checkedPlate = [];
                }


            },
            initUrlQueryInfo: function () {
                this.initPlate();
                this.initStocks();
                this.initKeyWords();
                this.initBulletin();
                this.initDate();
                this.initCheckedStr('checkedCategory', 'categoryListStock');
                this.initCheckedStr('checkedIndustry', 'industryList');
                this.initCheckedStr('checkedPlace', 'placeList');
                this.initCheckedStr('checkedOrg', 'orgList');


            },
            back: function () {
                if (document.referrer.search('cninfo.com.cn') > -1) {
                    window.history.back(-1);
                } else {
                    window.location.href =cninfo_data_url.replace("data","")+ '/new/commonUrl?url=disclosure/list/notice#szse/1';
                }
            }
        },
        created: function () {
            var _this = this;
            this.initUrlQueryInfo();
            this.getFundCompany();
            this.getHot();
            this.getStockList();
            this.getQuickSortList();
            if(_this.checkedSearchKeys.length>0){
                // _this.inputKeyword()
            }
            this.getHistory(function () {
                if (getUrlParam().lastPage == 'index' && localStorage.getItem('tabSearchItem')) {
                    var formIndexParams = JSON.parse(localStorage.getItem('tabSearchItem'));
                    _this.actMarket = formIndexParams.column;
                    _this.checkedStocks = formIndexParams.stock;
                    _this.checkedSearchKeys = formIndexParams.keyWord;
                    _this.checkedPlate = _this.plateList.filter(function (item) {
                        return formIndexParams.checkedPlate.filter(function (item2) {
                            return item.key == item2.key
                        }).length > 0 ? true : false;
                    })
                    _this.checkedIndustry = _this.industryList.filter(function (item) {
                        return formIndexParams.industry.filter(function (item2) {
                            return item.key == item2.key
                        }).length > 0 ? true : false;
                    })
                    //console.log('lastpage', _this.actMarket)
                    if (formIndexParams.date) {
                        _this.date = formIndexParams.date;
                        _this.dateChange(true);
                        //兼容ie10
                        // _this.$refs.datepicker.refInput[0].value = _this.date[0];
                        // _this.$refs.datepicker.refInput[1].value = _this.date[1];
                    } else {
                        _this.initDate();
                    }
                }

            });
        },
        mounted: function () {

            this.getAdPic();

        }
    })
}()
