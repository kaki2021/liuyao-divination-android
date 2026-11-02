package cn.guanxiang.liuyao;

public final class TestGongPlaceFormatter {
    private static void check(String expected, String actual) {
        if (!expected.equals(actual)) throw new AssertionError(expected + " != " + actual);
    }
    public static void main(String[] args) {
        check("四川省 成都市 武侯区", GongPlaceFormatter.format("CN","四川省","成都市","成都市","武侯区","中国"));
        check("北京市 海淀区", GongPlaceFormatter.format("CN","北京市","北京市","海淀区","中关村街道","中国"));
        check("四川省 成都市", GongPlaceFormatter.format("CN","四川省","成都市","成都市",null,"中国"));
        check("浙江省 金华市 义乌市", GongPlaceFormatter.format("CN","浙江省","金华市","义乌市",null,"中国"));
        check("California San Francisco", GongPlaceFormatter.format("US","California","San Francisco","San Francisco County","Mission District","United States"));
        check("中国", GongPlaceFormatter.format("CN",null,null,null,null,"中国"));
        System.out.println("PASS administrative-place formatting");
    }
}
