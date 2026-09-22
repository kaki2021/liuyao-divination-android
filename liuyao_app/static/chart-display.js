/* Deterministic display data. Bits and positions are always bottom to top.
 * HEXAGRAM_NAMES is generated from software_prep/hexagram_names.json.
 * This module does not assign changed-line relatives, shi/ying or body positions.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.LiuyaoChartDisplay = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  const STATES = Object.freeze({
    old_yin: Object.freeze({ bit: 0, moving: true }),
    young_yang: Object.freeze({ bit: 1, moving: false }),
    young_yin: Object.freeze({ bit: 0, moving: false }),
    old_yang: Object.freeze({ bit: 1, moving: true })
  });
  const TRIGRAMS = Object.freeze({
    '111': '乾', '110': '兑', '101': '离', '100': '震',
    '011': '巽', '010': '坎', '001': '艮', '000': '坤'
  });
  const HEXAGRAM_NAMES = Object.freeze({
    "111111": "乾为天",
    "011111": "天风姤",
    "001111": "天山遁",
    "000111": "天地否",
    "000011": "风地观",
    "000001": "山地剥",
    "000101": "火地晋",
    "111101": "火天大有",
    "110110": "兑为泽",
    "010110": "泽水困",
    "000110": "泽地萃",
    "001110": "泽山咸",
    "001010": "水山蹇",
    "001000": "地山谦",
    "001100": "雷山小过",
    "110100": "雷泽归妹",
    "101101": "离为火",
    "001101": "火山旅",
    "011101": "火风鼎",
    "010101": "火水未济",
    "010001": "山水蒙",
    "010011": "风水涣",
    "010111": "天水讼",
    "101111": "天火同人",
    "100100": "震为雷",
    "000100": "雷地豫",
    "010100": "雷水解",
    "011100": "雷风恒",
    "011000": "地风升",
    "011010": "水风井",
    "011110": "泽风大过",
    "100110": "泽雷随",
    "011011": "巽为风",
    "111011": "风天小畜",
    "101011": "风火家人",
    "100011": "风雷益",
    "100111": "天雷无妄",
    "100101": "火雷噬嗑",
    "100001": "山雷颐",
    "011001": "山风蛊",
    "010010": "坎为水",
    "110010": "水泽节",
    "100010": "水雷屯",
    "101010": "水火既济",
    "101110": "泽火革",
    "101100": "雷火丰",
    "101000": "地火明夷",
    "010000": "地水师",
    "001001": "艮为山",
    "101001": "山火贲",
    "111001": "山天大畜",
    "110001": "山泽损",
    "110101": "火泽睽",
    "110111": "天泽履",
    "110011": "风泽中孚",
    "001011": "风山渐",
    "000000": "坤为地",
    "100000": "地雷复",
    "110000": "地泽临",
    "111000": "地天泰",
    "111100": "雷天大壮",
    "111110": "泽天夬",
    "111010": "水天需",
    "000010": "水地比"
});
  const BRANCH_ELEMENTS = Object.freeze({
    '子': '水', '丑': '土', '寅': '木', '卯': '木', '辰': '土', '巳': '火',
    '午': '火', '未': '土', '申': '金', '酉': '金', '戌': '土', '亥': '水'
  });

  function trigram(bits) {
    return bits.includes(null) ? null : TRIGRAMS[bits.join('')];
  }

  function structure(bits, complete) {
    return {
      name: complete ? HEXAGRAM_NAMES[bits.join('')] : '待录入完整',
      bits: bits.slice(),
      upper_trigram: trigram(bits.slice(3)),
      lower_trigram: trigram(bits.slice(0, 3))
    };
  }

  function preview(lines) {
    if (!Array.isArray(lines) || lines.length !== 6) {
      throw new TypeError('Six bottom-to-top line states are required');
    }
    const bits = [];
    const moving_positions = [];
    let complete = true;
    for (let index = 0; index < 6; index += 1) {
      const line = lines[index];
      if (line === null) {
        bits.push(null);
        complete = false;
        continue;
      }
      if (typeof line !== 'string' || !Object.prototype.hasOwnProperty.call(STATES, line)) {
        throw new TypeError('Each line must be one of the four explicit states or null');
      }
      const definition = STATES[line];
      bits.push(definition.bit);
      if (definition.moving) moving_positions.push(index + 1);
    }
    return {
      complete,
      main: structure(bits, complete),
      changed_structure: complete && moving_positions.length > 0
        ? structure(bits.map((bit, index) => bit ^ Number(STATES[lines[index]].moving)), true)
        : null,
      moving_positions
    };
  }

  function branchElement(branch) {
    return typeof branch === 'string' && Object.prototype.hasOwnProperty.call(BRANCH_ELEMENTS, branch)
      ? BRANCH_ELEMENTS[branch] : null;
  }

  return Object.freeze({ preview, branchElement });
});
