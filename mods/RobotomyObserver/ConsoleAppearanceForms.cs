using System.Collections.Generic;using UnityEngine;
// Audited CURRENT controller states only. No parameters, thresholds or future phases.
public static class ConsoleAppearanceForms {
static readonly Dictionary<string,Dictionary<int,string>> forms=Build();
static Dictionary<string,Dictionary<int,string>> Build(){var all=new Dictionary<string,Dictionary<int,string>>();
all["BeautyBeastAnim"]=new Dictionary<int,string>();
all["BeautyBeastAnim"][Animator.StringToHash("beauty_default_ 건강_Baked")]="beauty_default_ 건강_Baked";
all["BeautyBeastAnim"][Animator.StringToHash("beauty_default_ 빈사_Baked")]="beauty_default_ 빈사_Baked";
all["BeautyBeastAnim"][Animator.StringToHash("beauty_default_ 죽음_Baked")]="beauty_default_ 죽음_Baked";
all["BigBadWolfAnim"]=new Dictionary<int,string>();
all["BigBadWolfAnim"][Animator.StringToHash("wolf_default_Baked")]="wolf_default_Baked";
all["BigBadWolfAnim"][Animator.StringToHash("wolf_full_Baked")]="wolf_full_Baked";
all["BigBadWolfAnim"][Animator.StringToHash("wolf_sharp_Baked")]="wolf_sharp_Baked";
all["BlackSwanAnim"]=new Dictionary<int,string>();
all["BlackSwanAnim"][Animator.StringToHash("Default")]="Default";
all["BlackSwanAnim"][Animator.StringToHash("Arms")]="Arms";
all["BlackSwanAnim"][Animator.StringToHash("Ears")]="Ears";
all["BlackSwanAnim"][Animator.StringToHash("Eye")]="Eye";
all["BlackSwanAnim"][Animator.StringToHash("Legs")]="Legs";
all["BlackSwanAnim"][Animator.StringToHash("Mouth")]="Mouth";
all["BlackSwanAnim"][Animator.StringToHash("Sis")]="Sis";
all["DangoCreatureAnim"]=new Dictionary<int,string>();
all["DangoCreatureAnim"][Animator.StringToHash("Level0_Default")]="Level0";
all["DangoCreatureAnim"][Animator.StringToHash("Level1_Attack")]="Level1";
all["DangoCreatureAnim"][Animator.StringToHash("Level1_Default 1")]="Level1";
all["DangoCreatureAnim"][Animator.StringToHash("Level1_Walk")]="Level1";
all["DangoCreatureAnim"][Animator.StringToHash("Level2_Attack")]="Level2";
all["DangoCreatureAnim"][Animator.StringToHash("Level2_Walk")]="Level2";
all["DangoCreatureAnim"][Animator.StringToHash("Level3_Attack_01")]="Level3";
all["DangoCreatureAnim"][Animator.StringToHash("Level3_Attack_02")]="Level3";
all["DangoCreatureAnim"][Animator.StringToHash("Level3_Attack_03")]="Level3";
all["DangoCreatureAnim"][Animator.StringToHash("Level3_Walk")]="Level3";
all["SakuraAnim"]=new Dictionary<int,string>();
all["SakuraAnim"][Animator.StringToHash("1_level_1")]="1_level_1";
all["SakuraAnim"][Animator.StringToHash("1_level_2")]="1_level_2";
all["SakuraAnim"][Animator.StringToHash("1_level_3")]="1_level_3";
all["SakuraAnim"][Animator.StringToHash("1_level_4")]="1_level_4";
all["ShyThingAnim"]=new Dictionary<int,string>();
all["ShyThingAnim"][Animator.StringToHash("default")]="default";
all["ShyThingAnim"][Animator.StringToHash("happyhappy")]="happyhappy";
all["ShyThingAnim"][Animator.StringToHash("happy")]="happy";
all["ShyThingAnim"][Animator.StringToHash("sad")]="sad";
all["ShyThingAnim"][Animator.StringToHash("sadsad")]="sadsad";
return all;}
public static string Form(string type,int state){Dictionary<int,string> map;string result;return forms.TryGetValue(type,out map)&&map.TryGetValue(state,out result)?result:null;}
}
