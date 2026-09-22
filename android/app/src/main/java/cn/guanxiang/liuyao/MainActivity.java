package cn.guanxiang.liuyao;

import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.webkit.*;
import android.webkit.CookieManager;
import android.widget.*;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final java.util.concurrent.ExecutorService FILES = Executors.newFixedThreadPool(2);
    private WebView web;
    private LinearLayout root;
    private ValueCallback<Uri[]> chooser;
    private File pendingExport;
    private boolean exporting;
    private String origin;
    private static final int CHOOSE_FILE=20, SAVE_FILE=21;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(245,244,239));
        root.setOnApplyWindowInsetsListener((v,insets)->{
            // Android 15 enforces edge-to-edge. Keep WebView, IME, and navigation separate.
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);}
            else v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);loading("观象", "正在准备你的六爻工作台…");
        AppRuntime.WORK.execute(()->{try {String url=AppRuntime.start(this);runOnUiThread(()->open(url));} catch(Exception e){runOnUiThread(()->failure());}});
    }
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void loading(String title,String detail){
        root.removeAllViews();LinearLayout panel=new LinearLayout(this);panel.setOrientation(LinearLayout.VERTICAL);panel.setGravity(Gravity.CENTER);panel.setPadding(dp(28),dp(30),dp(28),dp(30));
        TextView heading=new TextView(this);heading.setText(title);heading.setTextSize(32);heading.setTextColor(Color.rgb(35,63,55));heading.setGravity(Gravity.CENTER);panel.addView(heading);
        TextView body=new TextView(this);body.setText(detail);body.setTextSize(15);body.setGravity(Gravity.CENTER);body.setPadding(0,dp(18),0,0);panel.addView(body);root.addView(panel,new LinearLayout.LayoutParams(-1,-1));
    }
    private void failure(){loading("暂时未能启动", "已保存的案例不会被删除。请重新打开应用，或用完整安装包覆盖安装。");}
    @SuppressWarnings("SetJavaScriptEnabled") private void open(String url){
        if(isFinishing()||isDestroyed())return;origin=url;
        web=new WebView(this);web.setBackgroundColor(Color.rgb(245,244,239));
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportZoom(true);settings.setBuiltInZoomControls(true);settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);settings.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptCookie(true);CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        web.addJavascriptInterface(new NativeBridge(),"LiuyaoAndroid");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();
                if(local(uri.toString())){
                    if(uri.getPath().startsWith("/api/")){export(uri.toString(),uri.getPath().contains("rules")?"六爻规则库.xlsx":"六爻案例.json");return true;}
                    return false;
                }
                if(request.hasGesture()&&"https".equals(uri.getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(ActivityNotFoundException ignored){}
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                if(!local(request.getUrl().toString()))return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));
                return null;
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())toast("页面暂未加载成功，请重新打开应用。");}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/octet-stream"});
                try{startActivityForResult(intent,CHOOSE_FILE);}catch(ActivityNotFoundException e){chooser.onReceiveValue(null);chooser=null;toast("此手机没有可用的文件选择器。");}return true;
            }
            @Override public boolean onJsConfirm(WebView view,String url,String message,JsResult result){new AlertDialog.Builder(MainActivity.this).setMessage(message).setPositiveButton("确定",(d,w)->result.confirm()).setNegativeButton("取消",(d,w)->result.cancel()).setOnCancelListener(d->result.cancel()).show();return true;}
            @Override public boolean onJsAlert(WebView view,String url,String message,JsResult result){new AlertDialog.Builder(MainActivity.this).setMessage(message).setPositiveButton("知道了",(d,w)->result.confirm()).setOnCancelListener(d->result.confirm()).show();return true;}
        });
        web.setDownloadListener((downloadUrl,userAgent,disposition,mime,length)->export(downloadUrl,mime!=null&&mime.contains("spreadsheet")?"六爻规则库.xlsx":"六爻记录.json"));
        root.removeAllViews();root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        web.loadUrl(url,Collections.singletonMap("X-Liuyao-Bootstrap",AppRuntime.TOKEN));
    }
    private boolean local(String url){try{URI u=URI.create(url),base=URI.create(origin);return u.getUserInfo()==null&&u.getScheme().equals("http")&&u.getHost().equals("127.0.0.1")&&u.getPort()==base.getPort();}catch(Exception e){return false;}}
    private void toast(String message){runOnUiThread(()->Toast.makeText(this,message,Toast.LENGTH_LONG).show());}
    public final class NativeBridge {
        @JavascriptInterface public String readPreference(){return getPreferences(MODE_PRIVATE).getString("model","null");}
        @JavascriptInterface public void savePreference(String value){if(value!=null&&value.length()<2000)getPreferences(MODE_PRIVATE).edit().putString("model",value).apply();}
        @JavascriptInterface public String readDraft(){return getPreferences(MODE_PRIVATE).getString("draft","null");}
        @JavascriptInterface public void saveDraft(String value){if(value!=null&&value.length()<200000)getPreferences(MODE_PRIVATE).edit().putString("draft",value).apply();}
        @JavascriptInterface public void configureModel(String provider){runOnUiThread(()->credentials(provider));}
        @JavascriptInterface public void exportFile(String url,String filename){runOnUiThread(()->export(url,filename));}
        @JavascriptInterface public void analysisState(boolean busy){runOnUiThread(()->{
            if(busy){
                if(Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},30);
                try{startForegroundService(new Intent(MainActivity.this,AnalysisService.class));}catch(Exception ignored){toast("请暂时保持应用打开，等待分析完成。");}
            }
            // The native monitor stops after the server confirms completion, not after a tab change.
        });}
    }
    private void credentials(String provider){
        if(!provider.equals("deepseek")&&!provider.equals("doubao")){toast("离线演示无需密钥。");return;}
        final JSONObject current;
        try{current=new JSONObject(new SecretStore(this).read());}catch(Exception e){toast("密钥读取失败，请重新安装前先导出案例。");return;}
        LinearLayout fields=new LinearLayout(this);fields.setOrientation(LinearLayout.VERTICAL);fields.setPadding(dp(24),dp(12),dp(24),dp(8));
        TextView note=new TextView(this);note.setText("密钥仅加密保存在本机。留空会保留原密钥。");note.setTextSize(14);fields.addView(note);
        EditText key=new EditText(this);key.setSingleLine();key.setHint(current.has(provider.toUpperCase(Locale.ROOT)+"_API_KEY")?"已配置；输入新密钥可替换":"输入 API 密钥");key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);key.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);fields.addView(key,new LinearLayout.LayoutParams(-1,dp(56)));
        EditText model=new EditText(this);model.setSingleLine();model.setHint("豆包模型 ID 或接入点 ID");model.setText(current.optString("DOUBAO_MODEL",""));if(provider.equals("doubao"))fields.addView(model);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(provider.equals("deepseek")?"DeepSeek · Pro / max":"豆包 · 模型配置").setView(fields).setPositiveButton("保存",null).setNegativeButton("取消",null).setNeutralButton("清除密钥",null).create();
        dialog.setOnShowListener(d->{
            dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                try{String value=key.getText().toString().trim();if(!value.isEmpty())current.put(provider.toUpperCase(Locale.ROOT)+"_API_KEY",value);
                    if(provider.equals("doubao")){String m=model.getText().toString().trim();if(m.isEmpty()){model.setError("请填写模型 ID");return;}current.put("DOUBAO_MODEL",m);current.put("DOUBAO_MODELS",m);}saveCredentials(current,dialog);
                }catch(Exception e){toast("请检查配置内容。");}
            });
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->new AlertDialog.Builder(this).setMessage("清除此厂商在手机中保存的密钥？").setNegativeButton("取消",null).setPositiveButton("清除",(a,b)->{current.remove(provider.toUpperCase(Locale.ROOT)+"_API_KEY");saveCredentials(current,dialog);}).show());
        });dialog.show();
    }
    private void saveCredentials(JSONObject value,AlertDialog dialog){
        AppRuntime.WORK.execute(()->{try{
            if(!AppRuntime.configure(value.toString())){toast("正在分析，请完成后再修改模型配置。");return;}
            new SecretStore(this).save(value.toString());runOnUiThread(()->{dialog.dismiss();web.evaluateJavascript("window.LiuyaoApp.reloadConfig()",null);toast("配置已保存。");});
        }catch(Exception e){toast("配置未能保存，请检查后重试。");}});
    }
    private void export(String url,String filename){
        if(!local(url)||!URI.create(url).getPath().startsWith("/api/")){toast("无法导出此文件。");return;}
        if(exporting){toast("请先完成当前文件的保存。");return;}exporting=true;
        String safe=filename==null?"六爻记录.json":filename.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]","_");if(safe.length()>120)safe="六爻记录.json";final String name=safe;
        String cookie=CookieManager.getInstance().getCookie(origin);
        FILES.execute(()->{
            HttpURLConnection connection=null;File file=null;
            try{
                connection=(HttpURLConnection)new URL(url).openConnection(Proxy.NO_PROXY);connection.setConnectTimeout(10000);connection.setReadTimeout(30000);connection.setInstanceFollowRedirects(false);if(cookie!=null)connection.setRequestProperty("Cookie",cookie);
                if(connection.getResponseCode()!=200)throw new IOException("export failed");file=File.createTempFile("export-",".tmp",getCacheDir());
                try(InputStream in=connection.getInputStream();OutputStream out=new FileOutputStream(file)){byte[] buffer=new byte[16384];int n,total=0;while((n=in.read(buffer))>0){total+=n;if(total>50*1024*1024)throw new IOException("too large");out.write(buffer,0,n);}}
                pendingExport=file;
                runOnUiThread(()->{try{Intent save=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(name.endsWith(".xlsx")?"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":"application/json").putExtra(Intent.EXTRA_TITLE,name);startActivityForResult(save,SAVE_FILE);}catch(ActivityNotFoundException e){clearExport();toast("此手机没有可用的文件保存器。");}});
            }catch(Exception e){if(file!=null)file.delete();exporting=false;toast("导出未完成，请重试。");}finally{if(connection!=null)connection.disconnect();}
        });
    }
    private void clearExport(){if(pendingExport!=null)pendingExport.delete();pendingExport=null;exporting=false;}
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==CHOOSE_FILE&&chooser!=null){chooser.onReceiveValue(result==RESULT_OK&&data!=null&&data.getData()!=null?new Uri[]{data.getData()}:null);chooser=null;}
        if(request==SAVE_FILE){
            if(result!=RESULT_OK||data==null||pendingExport==null){clearExport();return;}
            Uri uri=data.getData();File file=pendingExport;
            AppRuntime.WORK.execute(()->{try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(uri)){if(out==null)throw new IOException();byte[] buffer=new byte[16384];int n;while((n=in.read(buffer))>0)out.write(buffer,0,n);toast("文件已保存。");}catch(Exception e){toast("文件未能保存，请重新导出。");}finally{clearExport();}});
        }
    }
    @Override public void onBackPressed(){
        if(web==null){super.onBackPressed();return;}
        web.evaluateJavascript("(function(){if(window.MobileUI&&window.MobileUI.back())return true;if(window.LiuyaoApp){if(!window.LiuyaoApp.canLeave())return true;window.LiuyaoApp.persistDraft();}return false;})()",result->{if(!"true".equals(result))moveTaskToBack(true);});
    }
    @Override protected void onPause(){if(web!=null)web.evaluateJavascript("window.LiuyaoApp&&window.LiuyaoApp.persistDraft()",null);super.onPause();}
    @Override protected void onDestroy(){if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}if(web!=null){web.removeJavascriptInterface("LiuyaoAndroid");web.destroy();}super.onDestroy();}
}
