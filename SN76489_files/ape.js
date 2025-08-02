/**
  Ape - Automatic embedding of video players and maps for PmWiki
  Written by (c) Petko Yotov 2014-2018    www.pmwiki.org/petko

  This text is written for PmWiki; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published
  by the Free Software Foundation version 2.

  Version 20180118
*/

(function() {
  var tags = {
    audio:  'audio',
    video:  'video',
    vtt:    'video',
    iframe: 'iframe',
    svg:    'object',
    swf:    'object'
  }
  var contenttypes = {
    flac: 'audio/x-flac',
    wav:  'audio/x-wav',
    mp3:  'audio/mpeg',
    ogg:  'audio/ogg',
    oga:  'audio/ogg',
    opus: 'audio/opus',

    ogv:  'video/ogg',
    mp4:  'video/mp4',
    webm: 'video/webm',
    vtt:  'text/vtt'
  }
  
  function log(x) {console.log(x);}
  
  function APgrab(tag, cn, par) {
    par = par || document;
    var i, r = [], rx = new RegExp('\\b'+cn+'\\b'), x = par.getElementsByTagName(tag);
    for(i=0;i<x.length; i++) if( (!cn) || rx.test(x[i].className)) r.push(x[i]);
    return r;
  }

  function APE() {
    var a, W, H, player, stl, i, j, k, links, href, src, d, scripts, players = [], ApeDir = '', allspans, idcnt = 0, rx, lnk, iheight= '315px', iwidth='560px', tn;
    scripts = APgrab('script');
    for(i=0; i<scripts.length; i++) {
      a = scripts[i].src.match(/^(.*\/)ape\.js(\?.*)?$/);
      if(! a) continue;
      ApeDir = a[1];
      break;
    }

    players = players.concat(APgrab('span', '(player|map|embed)'), APgrab('p', '(player|map|embed)'), 
                             APgrab('div',  '(player|map|embed)'), APgrab('dl', '(map|embed)'));

    rx = [ // more will be added in the future
      [/^https?:\/\/www\.(ted\.com\/talks\/\w+)$/i, 'https://embed-ssl.$1.html'],
      [/^https?:\/\/(www\.)?twitch\.tv\/videos\/(\d+)$/i, 'https://player.twitch.tv/?autoplay=false&video=v$2'],
      [/^https?:\/\/www\.youtube\.com\/watch\?v=([^&]+)(&.*)?$/i, 'https://www.youtube-nocookie.com/embed/$1$2'],
      [/^https?:\/\/www\.youtube\.com\/(playlist|videoseries)(.*)$/i, 'https://www.youtube-nocookie.com/embed/$1$2'],
      [/^https?:\/\/www\.youtube(-nocookie)?\.com(\/embed\/.*)$/i, 'https://www.youtube-nocookie.com/$2'],
      [/^https?:\/\/vimeo\.com\/(.*\/)?(\d+)$/i, 'https://player.vimeo.com/video/$2?title=0&byline=0&portrait=0&autoplay=0'],
      [/^https?(:\/\/www.dailymotion.com)(\/video\/[a-z0-9-]+)_/i, 'https$1embed/$2'],
      [/^https?:\/\/dai\.ly\/([a-z0-9-]+)$/i, 'https://www.dailymotion.com/embed/video/$1'],
      [/^https?:\/\/youtu\.be\/([^&?]+)([&?].*)?$/i, 'https://www.youtube-nocookie.com/embed/$1$2'],
      [/^https?:\/\/[a-z-]+\.facebook\.com\/photo\.php\?v=(\d+)$/i, 'https://www.facebook.com/video/embed?video_id=$1'],
      [/^https?:\/\/[a-z-]+\.facebook\.com\/\S+\/videos\/(\d+)\/?$/i, 'https://www.facebook.com/video/embed?video_id=$1'],
      [/^https?(:\/\/u\.osmfr\.org\/m\/\d+\/?)$/i, 'https$1'],
      [/^(http.*umap\.openstreetmap\.fr.*\/map\/[^\s]+)$/i, '$1'],
      [/^http.*openstreetmap\.org.*#map=[^\s]+$/i, ApeDir+'ape-osmap.html#'],
      [/^https?:\/\/osm\.org\/go\/\S+$/i, ApeDir+'ape-osmap.html#'],
      [/^https?(:\/\/archive\.org)\/(details|embed)\/([^\s\/]+)\/?$/i, 'https$1/embed/$3'],
      [/^https?(:\/\/(www\.)?teachertube\.com)\/(video|audio)\/[\w-]*-(\d+)\/?$/, 'https$1/embed/$3/$4'],
      [/^https?(:\/\/(www\.)?teachertube\.com)\/(video|audio)\/(\d+)\/?$/, 'https$1/embed/$3/$4'],
      [/^https?(:.*\.google\..*\/calendar\/embed.+)$/i, 'https$1'],
      [/^(https:\/\/drive\.google\.com\/open)\S*[?&]id=([_a-z0-9-]*)([&#].*)?$/i, 'https://www.google.com/maps/d/embed?mid=$2'],

      [/^https?.*\.youscribe\.com\/.*\/(\d+)($|\?.*$)/i, 'https://www.youscribe.com/BookReader/IframeEmbed?token=&width=auto&height=auto&startPage=1&displayMode=scroll&fullscreen=0&productId=$1'],    
      [/^https?.*\.youscribe\.com.*-(\d+)\/?$/i, 'https://www.youscribe.com/BookReader/IframeEmbed?token=&width=auto&height=auto&startPage=1&displayMode=scroll&fullscreen=0&productId=$1'],    
      [/^https?:\/\/(www\.)?vbox7\.com\/play:(\w+)/i, 'https://vbox7.com/emb/external.php?vid=$2'],
 
      [/^(https:\/\/docs\.google\.com\/[^?]*)(\?.*)?$/i, '$1?embedded=true'],
      [/^(.*\.(pdf|rtf))$/i, 'https://docs.google.com/gview?embedded=true&url=$1'],
      [/^(.*\.(docx?|xlsx?|pptx?|od[stp]))$/i, "https://view.officeapps.live.com/op/view.aspx?src=$1"],
      [/^(.*\.(dwg|dxf|plt|spl|stp|igs|sat|cgm))$/i, 'https://sharecad.org/cadframe/load?url=$1'],
 
      [/^(https:\/\/pastebin\.com)\/(embed(_i?frame|_js)?\/)?([\w-]+)/, '$1/embed_iframe/$4' ],
      [/^(.*\.svg)$/i, 'svg'],
      [/^(.*\.swf)$/i, 'swf'],
      [/^(.*\.(mp4|webm|ogv|vtt))$/i, 'video'],
      [/^(.*\.(mp3|opus|ogg|oga|flac))$/i, 'audio'],
      [/$^/, 'no comma after last element']
    ];
    // someday: http://img.youtube.com/vi/[your-video-id]/0.jpg
    
    var rx2 = [];
    if(typeof uAPErx == 'object') {
      for(var i=0; i<uAPErx.length; i++) rx2.push(uAPErx[i]);
    }
    for(var i=0; i<rx.length; i++) rx2.push(rx[i]);
    rx = rx2;

    for (i=0; i<players.length; i++) {
      player = players[i];
      tn = player.tagName.toLowerCase();
      stl = player.getAttribute('style');
      if(stl != null && typeof stl == 'object') { // MSIE<8
        stl="width:"+player.style.width+';'+" height:"+player.style.height+';'
      }
      if(stl) {
        a = stl.match(/width: *([0-9\.]+ *(%|p[xtc]|e[mx]|[mc]?m|v[wh]))/i)
        W = (a) ? a[1] : ((player.className.indexOf('map')<0)? iwidth : '100%');
        a = stl.match(/height: *([\d.]+ *(%|p[xtc]|e[mx]|[mc]?m|v[wh])|auto)/i)
        H = (a) ? a[1] : iheight;
      }
      else {
        W = (player.className.indexOf('map')<0)? iwidth : '100%';
        H = iheight;
      }

      if(tn=='span' || tn=='div'  || tn=='p' ) {
        links = APgrab('a', false, player);
        if(! links) continue;
 
        var sources = [ ];

        for (j=0; j<links.length; j++) {
          lnk = links[j];
          href = lnk.href;
          if(href.match(/[&?]action=upload(\&|$)/)) continue;
          for(k=0; k<rx.length; k++) {
            if(! href.match(rx[k][0])) continue;

            tag = 'iframe';
            src = href;
            if(typeof tags[ rx[k][1] ] != 'undefined') tag = rx[k][1];
            else  src = href.replace(rx[k][0], rx[k][1]);
            
            if(src.match(/#$/)) {
              if(!lnk.id) lnk.id = 'ape_id_'+(idcnt++);
              src += lnk.id;
            }
//             log([lnk, src, W, H, tag]);
            if(tag != 'video' && tag != 'audio') {
              APFrame(lnk, src, W, H, tag);
            }
            else sources.push(lnk);
            break;
          }
        }
        if(sources.length) {
          APFrame(player, sources, W, H, tag);
        }
      }
      else if(tn=='dl') {
        if(!player.id) player.id = 'ape_id_'+(idcnt++);
        APFrame(player, ApeDir+'ape-osmap.html#'+player.id, W, H, 'iframe');
      }
    }
  }

  function APFrame(elm, src, W, H, tag) {
    var d = document.createElement(tags[tag]);
    
    var align = '';
    if(elm.style.textAlign.indexOf("center")>=0) align = "margin: 0 auto;";
    if(elm.style.textAlign.indexOf("right")>=0) align = "margin: 0 0 0 auto;";

    var attrs = {
      iframe: {
        id: (elm.id)?'iframe_'+elm.id:'',
        src: src,
        style: "border: 1px solid black; display: block; width: "+W+"; height: "+H+";"+align,
        frameborder: 0,
        marginheight: 0,
        marginwidth: 0,
        webkitallowfullscreen: '=',
        mozallowfullscreen: '=',
        msallowfullscreen: '=',
        oallowfullscreen: '=',
        allowfullscreen: '='
      },
      audio: {
        id: (elm.id)?'audio_'+elm.id:'',
        style: align,
        controls: '='
      },
      swf: {
        id: (elm.id)?'swf_'+elm.id:'',
        style: "border: 1px solid black; display: block; width: "+W+"; height: "+H+";"+align,
        type: "application/x-shockwave-flash",
        quality: 'high',
        data: src
      },
      svg: {
        id: (elm.id)?'svg_'+elm.id:'',
        style:"border: none; display: inline; width: "+W+"; height: "+H+";"+align,
        type: 'image/svg+xml',
        data: src
      }
    };
    
    inaudiovideo = '';
    if(tag == 'video' || tag == 'audio') {
      attrs.video = { };
      for (i in attrs.iframe) {
        if(i == 'id' || i == 'src') continue;
        attrs.video[i] = attrs.iframe[i];
      }
      attrs.video.controls = '=';
      subs = 0;
      for(var i=0; i<src.length; i++) {
        var href = src[i].href;
//         log(href);
        var a = href.toLowerCase().match(/\.(\w+)$/);
//         log(a);
        var tp = '';
        if(a) {
          if(typeof contenttypes[a[1]] != 'undefined') {
            tp = contenttypes[a[1]];
            var title = src[i].getAttribute('title');
            if(title) {
              var b = title.match(/\b(codecs=\S+)(\s|$)/);
              if (b) tp += '; '+a[1];
            }
          }
        }
        if(tp) tp=' type="'+tp+'"';
        if(a[1] == 'vtt') {
          var dflt = subs ? '' : ' default';
          var lang = title ? ' srclang="'+title+'"' : '';
          subs++;
          inaudiovideo += '<track src="'+href+'" kind="subtitles" label="'+src[i].textContent+'"'+lang+dflt+' >';
        }
        else inaudiovideo += '<source src="'+href+'" '+tp+'>';
      }
    }
    
    var inner = {
      iframe: '',
      audio: inaudiovideo,
      video: inaudiovideo,
      swf: 'embed',
      svg: 'embed'
    }
    
    for(var i in attrs[tag]) {
      var val = attrs[tag][i];
      if(!val) continue;
      if(val == '=') val = i;
      else if (typeof val == 'array') continue;
      d.setAttribute(i, val);   
    }
    
    if(inner[tag]) {
      var ih = (inner[tag]!='embed')
        ? inner[tag]
        : '<embed type="'+attrs[tag].type+'" src="'
            +src+'" style="'+attrs[tag].style+'" />'
      d.innerHTML = ih;
    }
    
    
    elm.parentNode.insertBefore(d, elm);
    elm.style.display = 'none';
    if(H=='auto') {
      var realw = d.offsetWidth;
      var realh = Math.round(realw / 16 * 9);
      d.style.height = realh + "px";
    }
  }

  setTimeout(APE, 50);

})();

