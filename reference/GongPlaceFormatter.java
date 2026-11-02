package cn.guanxiang.liuyao;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Format administrative areas without inventing a county or including a street. */
final class GongPlaceFormatter {
    private static String clean(String value) { return value == null ? "" : value.trim(); }
    private static boolean district(String value) {
        return value.endsWith("区") || value.endsWith("县") || value.endsWith("旗") || value.endsWith("市");
    }
    private static void add(List<String> values, String value) {
        if (!value.isEmpty() && !values.contains(value)) values.add(value);
    }
    static String format(String code, String admin, String locality, String subAdmin, String subLocality, String country) {
        String province=clean(admin), city=clean(locality), sub=clean(subAdmin), area=clean(subLocality);
        boolean china="CN".equals(clean(code).toUpperCase(Locale.ROOT));
        List<String> parts=new ArrayList<>();
        add(parts, province);
        if (!city.isEmpty()) add(parts, city);
        else if (!sub.isEmpty()) { add(parts, sub); sub=""; }
        if (china) {
            if (district(area)) add(parts, area);
            else if (district(sub)) add(parts, sub);
        }
        if (parts.isEmpty()) add(parts, clean(country));
        return String.join(" ", parts);
    }
}
