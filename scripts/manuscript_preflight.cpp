// C++20 static manuscript preflight. No TeX macro expansion or mathematical approval.
// Only local literal input/include/bibliography dependencies are accepted.
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
struct Location { fs::path path; size_t line; };
static std::string trim(std::string s) {
    auto a=s.find_first_not_of(" \t\r\n"), b=s.find_last_not_of(" \t\r\n");
    return a==std::string::npos ? "" : s.substr(a,b-a+1);
}
static std::string lower(std::string s) {
    for (char& c:s) c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}
static std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> v; std::istringstream in(s); std::string part;
    while (std::getline(in,part,',')) v.push_back(trim(part));
    return v;
}
static std::string read(const fs::path& path) {
    std::ifstream f(path,std::ios::binary);
    if (!f) throw std::runtime_error("cannot read "+path.string());
    return {std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>()};
}
static void whitespace(const std::string& s,size_t& i) {
    while (i<s.size()&&std::isspace(static_cast<unsigned char>(s[i]))) ++i;
}
static bool escaped(const std::string& s,size_t i) {
    size_t n=0; while (i>0&&s[--i]=='\\') ++n; return n%2!=0;
}
static std::string command(const std::string& s,size_t& i) {
    if (i>=s.size()||s[i]!='\\') throw std::runtime_error("expected TeX control sequence");
    ++i; size_t start=i;
    if (i<s.size()&&std::isalpha(static_cast<unsigned char>(s[i]))) {
        while(i<s.size()&&std::isalpha(static_cast<unsigned char>(s[i])))++i;
    } else if (i<s.size()) ++i;
    return s.substr(start,i-start);
}
static std::string argument(const std::string& s,size_t& i,char open='{',char close='}') {
    whitespace(s,i);
    if(i>=s.size()||s[i]!=open)throw std::runtime_error(std::string("expected literal ")+open+" argument");
    size_t start=++i; int level=1,braces=0;
    for(;i<s.size();++i){
        if(escaped(s,i))continue;
        if(open=='['){
            if(s[i]=='{'){++braces;continue;}
            if(s[i]=='}'){--braces;if(braces<0)throw std::runtime_error("unbalanced optional argument");continue;}
            if(braces)continue;
        }
        if(s[i]==open)++level;
        else if(s[i]==close){--level;if(level==0){auto result=s.substr(start,i-start);++i;return result;}}
    }
    throw std::runtime_error("unterminated TeX argument");
}
static void options(const std::string& s,size_t& i) {
    whitespace(s,i);if(i<s.size()&&s[i]=='*')++i;
    whitespace(s,i);while(i<s.size()&&s[i]=='['){argument(s,i,'[',']');whitespace(s,i);}
}
static bool literal(const std::string& s) {
    return !s.empty()&&s.find_first_of("\\{}#$~%^&\r\n\t ")==std::string::npos;
}
static bool key(const std::string& s) {
    return !s.empty()&&s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._/-+@")==std::string::npos;
}
static void mask(std::string& s,size_t a,size_t b) {
    for(size_t i=a;i<b;++i)if(s[i]!='\n')s[i]=' ';
}
// Preserve offsets/newlines. Comments obey backslash parity; verbatim bodies are
// masked before dependency scanning, so printed TeX examples are not dependencies.
static std::string lexical_source(const std::string& raw) {
    std::string s=raw;
    for(size_t i=0;i<s.size();){
        if(s[i]=='%'&&!escaped(s,i)){
            auto end=s.find('\n',i);if(end==std::string::npos)end=s.size();mask(s,i,end);i=end;continue;
        }
        if(s[i]!='\\'){++i;continue;}
        size_t start=i;auto cmd=command(s,i);
        if(cmd=="verb"){
            if(i<s.size()&&s[i]=='*')++i;
            if(i>=s.size()||std::isspace(static_cast<unsigned char>(s[i])))throw std::runtime_error("unsupported verb syntax");
            char delimiter=s[i++];auto end=s.find(delimiter,i);
            if(end==std::string::npos)throw std::runtime_error("unterminated verb");
            mask(s,start,end+1);i=end+1;
        }else if(cmd=="begin"){
            size_t probe=i;whitespace(s,probe);
            if(probe<s.size()&&s[probe]=='{'){
                auto env=argument(s,probe);
                if(env=="verbatim"||env=="verbatim*"||env=="lstlisting"||env=="minted"||env=="comment"){
                    std::string marker="\\end{"+env+"}";auto end=s.find(marker,probe);
                    if(end==std::string::npos)throw std::runtime_error("unterminated literal environment "+env);
                    mask(s,start,end+marker.size());i=end+marker.size();
                }
            }
        }
    }
    return s;
}

class Preflight {
    fs::path root;
    std::map<fs::path,size_t> active;
    std::set<fs::path> bibs,assets,stack;
    std::vector<std::string> edges;
    std::map<std::string,std::vector<Location>> labels,refs,citations,bibkeys;
    size_t errors=0,comments=0,pathflags=0,draftflags=0,dynamicflags=0;
    std::string relative(const fs::path& p)const{return fs::relative(p,root).generic_string();}
    size_t lineno(const std::string& text,size_t pos)const{return 1+std::count(text.begin(),text.begin()+static_cast<std::ptrdiff_t>(pos),'\n');}
    void error(const Location& loc,const std::string& text){++errors;std::cerr<<"ERROR "<<relative(loc.path)<<':'<<loc.line<<": "<<text<<'\n';}
    void dynamic(const Location& loc,const std::string& text){++dynamicflags;error(loc,"unsupported dynamic/control syntax: "+text);}
    fs::path dependency(std::string name,const std::string& extension,const Location& loc){
        if(!literal(name)||fs::path(name).is_absolute())throw std::runtime_error("nonliteral or absolute dependency "+name);
        fs::path rel(name);for(const auto& component:rel)if(component=="..")throw std::runtime_error("parent traversal dependency "+name);
        fs::path p=root/rel;
        if(!fs::is_regular_file(p)&&p.extension().empty())p+=extension;
        if(!fs::is_regular_file(p))throw std::runtime_error("missing dependency "+name+" (resolved from manuscript root)");
        p=fs::canonical(p);auto local=fs::relative(p,root);
        if(local.empty()||*local.begin()=="..")throw std::runtime_error("dependency escapes manuscript root "+name);
        edges.push_back(relative(loc.path)+":"+std::to_string(loc.line)+" -> "+relative(p));
        return p;
    }
    void keys(const std::string& values,std::map<std::string,std::vector<Location>>& target,const Location& loc,bool citation=false){
        for(const auto& item:split(values)){
            if(item=="*"){error(loc,"wildcard citation/reference prohibited (including nocite{*})");continue;}
            if(!key(item)){dynamic(loc,(citation?"citation":"label/reference")+std::string(" key ")+item);continue;}
            target[item].push_back(loc);
        }
    }
    void scan_hazards(const fs::path& p,const std::string& raw){
        static const std::regex paths(R"((/(home|Users|media|mnt|workspace|tmp|root)/|file://|sandbox:|[A-Za-z]:\\(Users|Documents|Temp|Windows|workspace)\\|\$\{?(HOME|CODEX_HOME)\}?|private[ _-]+(repo(sitory)?|artifact|path)))",std::regex::icase);
        static const std::regex draft(R"((\b(TODO|FIXME|TBD|XXX|PLACEHOLDER)\b|\bDRAFT(ING)?[ _-]+(NOTE|ONLY)\b|\bAUTHOR[ _-]+(QUERY|TODO|NOTE)\b|\bQ0[1-9]\b|\bQ10\b|IMPLEMENTATION_BRIEF|CHANGE_QUEUE|REVISION_AND_RELEASE_PLAN|writing[ _-]+report|report_[AB]\.md|\\todo\b))",std::regex::icase);
        std::istringstream in(raw);std::string line;size_t n=0;
        while(std::getline(in,line)){
            ++n;std::smatch match;
            if(std::regex_search(line,match,paths)){++pathflags;error({p,n},"private/local path marker: "+match.str());}
            if(std::regex_search(line,match,draft)){++draftflags;error({p,n},"draft/internal note marker: "+match.str());}
            for(size_t i=0;i<line.size();++i)if(line[i]=='%'&&!escaped(line,i)){++comments;break;}
        }
    }
    void parse_tex(const fs::path& p){
        if(stack.contains(p))throw std::runtime_error("cyclic TeX dependency "+relative(p));
        if(stack.size()>128)throw std::runtime_error("TeX dependency depth exceeds 128");
        stack.insert(p);auto raw=read(p);
        if(++active[p]==1)scan_hazards(p,raw);
        auto source=lexical_source(raw);
        const std::set<std::string> refcmds{"ref","eqref","pageref","autoref","nameref","cref","Cref","cpageref","Cpageref","vref","Vref"};
        const std::set<std::string> macros{"newcommand","renewcommand","providecommand","DeclareRobustCommand","newcolumntype"};
        for(size_t i=0;i<source.size();){
            if(source[i]!='\\'){++i;continue;}
            size_t start=i;auto cmd=command(source,i);Location loc{p,lineno(source,start)};
            try{
                if(cmd=="input"||cmd=="include"){
                    auto name=trim(argument(source,i));
                    if(!literal(name)){dynamic(loc,"dependency "+name);continue;}
                    parse_tex(dependency(name,".tex",loc));
                }else if(cmd=="bibliography"){
                    for(const auto& name:split(argument(source,i)))bibs.insert(dependency(name,".bib",loc));
                }else if(cmd=="addbibresource"){
                    options(source,i);bibs.insert(dependency(trim(argument(source,i)),".bib",loc));
                }else if(cmd=="includegraphics"){
                    options(source,i);auto name=trim(argument(source,i));
                    if(!literal(name)){dynamic(loc,"graphics dependency "+name);continue;}
                    if(fs::path(name).extension().empty()){
                        std::vector<std::string> found;
                        for(const auto& ext:{".pdf",".png",".jpg",".jpeg",".eps"})if(fs::is_regular_file(root/(name+ext)))found.push_back(name+ext);
                        if(found.size()!=1)throw std::runtime_error("graphics extension absent/ambiguous: "+name);
                        name=found.front();
                    }
                    assets.insert(dependency(name,"",loc));
                }else if(cmd=="label"){
                    options(source,i);auto name=trim(argument(source,i));
                    if(!key(name))dynamic(loc,"label "+name);else labels[name].push_back(loc);
                }else if(refcmds.contains(cmd)){
                    options(source,i);keys(argument(source,i),refs,loc);
                }else if(cmd=="crefrange"||cmd=="Crefrange"){
                    options(source,i);keys(argument(source,i),refs,loc);keys(argument(source,i),refs,loc);
                }else if(cmd=="hyperref"){
                    whitespace(source,i);if(i<source.size()&&source[i]=='[')keys(argument(source,i,'[',']'),refs,loc);
                }else if(lower(cmd).find("cite")!=std::string::npos&&cmd!="citestyle"&&cmd!="setcitestyle"){
                    options(source,i);keys(argument(source,i),citations,loc,true);
                }else if(macros.contains(cmd)){
                    whitespace(source,i);if(i<source.size()&&source[i]=='*')++i;whitespace(source,i);
                    if(i<source.size()&&source[i]=='{')argument(source,i);else command(source,i);
                    options(source,i);auto body=argument(source,i);
                    static const std::regex critical(R"(\\(input|include|includegraphics|bibliography|addbibresource|label|[A-Za-z]*cite[A-Za-z]*|ref|eqref|cref|Cref)\b)");
                    if(std::regex_search(body,critical))dynamic(loc,"dependency/citation/label hidden in macro definition");
                }else if(cmd=="string"){
                    whitespace(source,i);if(i<source.size()&&source[i]=='\\')command(source,i);else if(i<source.size())++i;
                }else if(cmd=="end"){
                    size_t probe=i;whitespace(source,probe);
                    if(probe<source.size()&&source[probe]=='{'){
                        auto env=argument(source,probe);
                        if(env=="document"){
                            auto trailing=trim(source.substr(probe));if(!trailing.empty())dynamic(loc,"content after end{document}");
                            break;
                        }
                    }
                }else if((cmd.rfind("if",0)==0&&cmd!="iff")||cmd=="else"||cmd=="fi"||cmd=="IfFileExists"||cmd=="InputIfFileExists"||cmd=="includeonly"||cmd=="subfile"||cmd=="import"||cmd=="subimport"||cmd=="graphicspath"||cmd=="newif"||cmd=="def"||cmd=="gdef"||cmd=="edef"||cmd=="xdef"||cmd=="let"||cmd=="csname"||cmd=="expandafter"||cmd=="catcode"||cmd=="endinput"||cmd=="newenvironment"||cmd=="renewenvironment"||cmd=="makeatletter"||cmd=="inputminted"||cmd=="lstinputlisting"||cmd=="includepdf"||cmd=="special"||cmd=="openin"||cmd=="read"){
                    dynamic(loc,"\\"+cmd);
                }
            }catch(const std::exception& e){error(loc,e.what());}
        }
        stack.erase(p);
    }
    void parse_bib(const fs::path& p){
        auto raw=read(p);scan_hazards(p,raw);auto s=lexical_source(raw);
        for(size_t i=0;i<s.size();){
            if(s[i]!='@'){++i;continue;}
            size_t start=i++;std::string type;
            while(i<s.size()&&std::isalpha(static_cast<unsigned char>(s[i])))type+=s[i++];
            whitespace(s,i);if(i==s.size()||(s[i]!='{'&&s[i]!='(')){error({p,lineno(s,start)},"malformed BibTeX entry");continue;}
            char open=s[i++],close=open=='{'?'}':')';size_t content=i;
            int braces=open=='{'?1:0;bool quote=false;bool ended=false;
            for(;i<s.size();++i){
                if(escaped(s,i))continue;
                char c=s[i];
                if(c=='"'&&braces==(open=='{'?1:0)){quote=!quote;continue;}
                if(c=='{')++braces;
                else if(c=='}'){
                    --braces;if(open=='{'&&braces==0&&!quote){ended=true;break;}
                }else if(c==close&&open=='('&&braces==0&&!quote){ended=true;break;}
            }
            Location loc{p,lineno(s,start)};
            if(!ended){error(loc,"unterminated BibTeX entry");break;}
            auto body=s.substr(content,i-content);++i;type=lower(type);
            if(type=="comment"||type=="preamble"||type=="string")continue;
            auto comma=body.find(',');auto name=trim(body.substr(0,comma));
            if(comma==std::string::npos||!key(name))error(loc,"malformed/dynamic bibliography key "+name);
            else bibkeys[name].push_back(loc);
        }
    }
public:
    explicit Preflight(fs::path base):root(std::move(base)){}
    bool run(const fs::path& main,const fs::path& destination){
        parse_tex(main);
        if(bibs.empty())error({main,1},"no active bibliography declared");
        for(const auto& p:bibs)parse_bib(p);
        size_t duplicate_bib=0,unused=0,missing=0,duplicate_labels=0,missing_refs=0;
        for(const auto& [name,locs]:bibkeys){
            if(locs.size()>1){++duplicate_bib;error(locs.front(),"duplicate bibliography key "+name);}
            if(!citations.contains(name)){++unused;error(locs.front(),"unused bibliography key "+name);}
        }
        for(const auto& [name,locs]:citations)if(!bibkeys.contains(name)){++missing;error(locs.front(),"missing bibliography key "+name);}
        for(const auto& [name,locs]:labels)if(locs.size()>1){++duplicate_labels;error(locs.front(),"duplicate label "+name);}
        for(const auto& [name,locs]:refs)if(!labels.contains(name)){++missing_refs;error(locs.front(),"undefined reference "+name);}
        std::cout<<"MANUSCRIPT_ROOT="<<root.generic_string()<<"\nSTATIC_ACTIVE_SOURCE_GRAPH\n";
        for(const auto& [p,count]:active)std::cout<<"ACTIVE_TEX "<<relative(p)<<" occurrences="<<count<<'\n';
        for(const auto& p:bibs)std::cout<<"ACTIVE_BIB "<<relative(p)<<'\n';
        for(const auto& p:assets)std::cout<<"ACTIVE_ASSET "<<relative(p)<<'\n';
        for(const auto& edge:edges)std::cout<<"DEPENDENCY "<<edge<<'\n';
        size_t ref_uses=0,cite_uses=0;for(const auto& [k,v]:refs){(void)k;ref_uses+=v.size();}for(const auto& [k,v]:citations){(void)k;cite_uses+=v.size();}
        std::cout<<"active_tex_files="<<active.size()<<"\nactive_bib_files="<<bibs.size()<<"\nactive_assets="<<assets.size()
            <<"\nbib_entries="<<bibkeys.size()<<"\ncited_unique="<<citations.size()<<"\ncitation_key_occurrences="<<cite_uses
            <<"\nunused_entries="<<unused<<"\nmissing_entries="<<missing<<"\nduplicate_bib_keys="<<duplicate_bib
            <<"\nlabels="<<labels.size()<<"\nreference_keys="<<refs.size()<<"\nreference_occurrences="<<ref_uses
            <<"\nduplicate_labels="<<duplicate_labels<<"\nundefined_reference_keys="<<missing_refs
            <<"\nraw_percent_comment_candidates="<<comments<<"\nprivate_local_path_flags="<<pathflags<<"\ndraft_note_flags="<<draftflags
            <<"\nunsupported_dynamic_flags="<<dynamicflags<<"\nerrors="<<errors<<'\n';
        std::cout<<"LIMITATION=static literal-source analysis; no general TeX expansion, semantic proof check, bibliography accuracy check, or PDF approval\n";
        if(!destination.empty()){
            if(errors)std::cout<<"ACTIVE_EXPORT=NOT_CREATED (preflight errors)\n";
            else{
                if(fs::exists(destination))throw std::runtime_error("export destination already exists");
                fs::create_directories(destination);std::set<fs::path> files=bibs;files.insert(assets.begin(),assets.end());
                for(const auto& [p,count]:active){(void)count;files.insert(p);}
                for(const auto& p:files){auto target=destination/fs::relative(p,root);fs::create_directories(target.parent_path());fs::copy_file(p,target);}
                std::cout<<"ACTIVE_EXPORT="<<fs::absolute(destination).generic_string()<<" files="<<files.size()<<'\n';
            }
        }
        std::cout<<"MANUSCRIPT_PREFLIGHT="<<(errors?"FAIL":"PASS")<<'\n';return errors==0;
    }
};
int main(int argc,char** argv){
    try{
        if(argc!=2&&argc!=4)throw std::runtime_error("usage: manuscript_preflight PAPER.TEX [--export NEW_DIRECTORY]");
        fs::path main=fs::canonical(argv[1]),export_path;
        if(argc==4){if(std::string(argv[2])!="--export")throw std::runtime_error("expected --export");export_path=argv[3];}
        Preflight checker(main.parent_path());return checker.run(main,export_path)?0:1;
    }catch(const std::exception& e){std::cerr<<"FATAL "<<e.what()<<'\n';return 2;}
}
