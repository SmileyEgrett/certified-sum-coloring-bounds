// C++20 bounded check of the three identified DSJC500.9 continuous endpoints.
// Fixed input bytes are authenticated before parsing; this is an authentic-data
// cross-check, not a general certificate-language or resource-safety verifier.
// Exact arithmetic uses nonnegative base-10^9 integers; no optimization is run.
#include <algorithm>
#include <array>
#include <bitset>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <openssl/sha.h>
namespace fs = std::filesystem;
void need(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
std::string bytes(const fs::path&p){std::ifstream f(p,std::ios::binary);need(bool(f),"cannot open "+p.string());return {std::istreambuf_iterator<char>(f),{}};}
std::string hash(const std::string&s){unsigned char h[SHA256_DIGEST_LENGTH];SHA256(reinterpret_cast<const unsigned char*>(s.data()),s.size(),h);std::ostringstream o;o<<std::hex<<std::setfill('0');for(auto x:h)o<<std::setw(2)<<unsigned(x);return o.str();}
constexpr const char* graph_sha256="95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39";
constexpr const char* census_sha256="60f50a2de470d7fe6925d9b327cecc017def5a346723fc011b2817f9ada3e27f";
constexpr const char* reconstruction_sha256="95758a2d7144dbc84c3a032237ccef0a4cc554d9385e7d4e2cb4d98fd372c19c";
const std::array<std::pair<const char*,const char*>,3> point_files={{
 {"P5E_fractional_exact.json","25e14e3725e7629f4edce87dcb60848755edf5109ad8fc7fb1574d423cdaea5b"},
 {"P5F_fractional_exact.json","9e3f7e8d3d2e70c00bbb9ac4fcce230829690f60cc2fdb12a5dd3a6087391285"},
 {"P7F_fractional_exact.json","187ea34d08ebc1d4840cf11240656f7bc836572273735ef36aece92b6967e147"}
}};
std::string bound_bytes(const fs::path&path,const char*expected,const std::string&name){
 auto raw=bytes(path);need(hash(raw)==expected,"input byte identity: "+name);return raw;
}
struct Inputs {
 std::string graph,census,reconstruction;std::array<std::string,3>points;
 Inputs(const fs::path&g,const fs::path&p,const fs::path&c){
  graph=bound_bytes(g,graph_sha256,"graph");
  census=bound_bytes(c,census_sha256,"unresolved census");
  const auto point_dir=fs::canonical(p);
  need(fs::is_directory(point_dir),"point directory");
  reconstruction=bound_bytes(point_dir.parent_path()/"reconstruction.json",reconstruction_sha256,"reconstruction");
  for(std::size_t i=0;i<points.size();++i)
   points[i]=bound_bytes(point_dir/point_files[i].first,point_files[i].second,point_files[i].first);
 }
};
struct Big {
 static constexpr std::uint64_t B=1000000000;std::vector<std::uint32_t>d{0};
 explicit Big(std::string s="0"){need(!s.empty()&&(s.size()==1||s[0]!='0'),"noncanonical nonnegative integer");for(char c:s)need(c>='0'&&c<='9',"noninteger proof field");d.clear();for(std::size_t e=s.size();e;){std::size_t b=e>9?e-9:0;d.push_back(static_cast<std::uint32_t>(std::stoul(s.substr(b,e-b))));e=b;}trim();}
 void trim(){while(d.size()>1&&d.back()==0)d.pop_back();}
 int cmp(const Big&b)const{if(d.size()!=b.d.size())return d.size()<b.d.size()?-1:1;for(std::size_t i=d.size();i--;)if(d[i]!=b.d[i])return d[i]<b.d[i]?-1:1;return 0;}
 Big&add(const Big&b){d.resize(std::max(d.size(),b.d.size()),0);std::uint64_t carry=0;for(std::size_t i=0;i<d.size();++i){auto t=std::uint64_t(d[i])+(i<b.d.size()?b.d[i]:0)+carry;d[i]=t%B;carry=t/B;}if(carry)d.push_back(carry);return *this;}
 Big minus(const Big&b)const{need(cmp(b)>=0,"negative integer subtraction");Big c=*this;std::int64_t borrow=0;for(std::size_t i=0;i<c.d.size();++i){auto t=std::int64_t(c.d[i])-(i<b.d.size()?b.d[i]:0)-borrow;if(t<0){t+=B;borrow=1;}else borrow=0;c.d[i]=t;}need(borrow==0,"subtraction borrow");c.trim();return c;}
 Big times(std::uint32_t m)const{Big c=*this;std::uint64_t carry=0;for(auto&v:c.d){auto t=std::uint64_t(v)*m+carry;v=t%B;carry=t/B;}while(carry){c.d.push_back(carry%B);carry/=B;}c.trim();return c;}
 std::string str()const{std::ostringstream o;o<<d.back();for(std::size_t i=d.size()-1;i--;)o<<std::setw(9)<<std::setfill('0')<<d[i];return o.str();}
};
struct J {enum Kind{object,array,string,number,literal}kind;std::string s;std::vector<J>a;std::map<std::string,J>o;
 const J&at(const std::string&k)const{need(kind==object&&o.count(k),"missing object field "+k);return o.at(k);}J&at(const std::string&k){need(kind==object&&o.count(k),"missing object field "+k);return o.at(k);}
 std::string text()const{need(kind==string,"expected string");return s;}Big big()const{need(kind==number,"expected numeric integer");return Big(s);}int integer()const{auto b=big();need(b.cmp(Big("1000000000"))<0,"oversized small integer");return std::stoi(s);}
};
struct Parser {
 const std::string&s;std::size_t p=0;unsigned depth=0;
 void ws(){while(p<s.size()&&std::isspace(static_cast<unsigned char>(s[p])))++p;}
 char peek(){ws();need(p<s.size(),"unexpected JSON end");return s[p];}
 std::string string(){need(s[p++]=='"',"string opener");std::string r;while(p<s.size()){char c=s[p++];if(c=='"')return r;need(static_cast<unsigned char>(c)>=32,"control in string");if(c=='\\'){need(p<s.size(),"escape end");char x=s[p++];switch(x){case '"':case '\\':case '/':r+=x;break;case 'n':r+='\n';break;case 'r':r+='\r';break;case 't':r+='\t';break;case 'b':r+='\b';break;case 'f':r+='\f';break;default:throw std::runtime_error("unsupported escaped string in bounded input parser");}}else r+=c;}throw std::runtime_error("unterminated string");}
 J value(){need(++depth<=50,"JSON depth");char c=peek();J v;
  if(c=='{'){v.kind=J::object;++p;if(peek()!='}')for(;;){need(peek()=='"',"object key");auto k=string();need(peek()==':',"object colon");++p;need(v.o.emplace(k,value()).second,"duplicate JSON key");char z=peek();if(z=='}')break;need(z==',',"object separator");++p;}++p;}
  else if(c=='['){v.kind=J::array;++p;if(peek()!=']')for(;;){v.a.push_back(value());char z=peek();if(z==']')break;need(z==',',"array separator");++p;}++p;}
  else if(c=='"'){v.kind=J::string;v.s=string();}
  else {auto start=p;while(p<s.size()&&s[p]!=','&&s[p]!=']'&&s[p]!='}'&&!std::isspace(static_cast<unsigned char>(s[p])))++p;v.s=s.substr(start,p-start);need(!v.s.empty(),"empty token");if(v.s=="true"||v.s=="false"||v.s=="null")v.kind=J::literal;else{v.kind=J::number;std::size_t i=0;if(v.s[i]=='-')++i;need(i<v.s.size(),"invalid number");if(v.s[i]=='0')++i;else {need(v.s[i]>='1'&&v.s[i]<='9',"invalid number start");while(i<v.s.size()&&std::isdigit(static_cast<unsigned char>(v.s[i])))++i;}if(i<v.s.size()&&v.s[i]=='.'){++i;auto b=i;while(i<v.s.size()&&std::isdigit(static_cast<unsigned char>(v.s[i])))++i;need(i>b,"empty fraction");}if(i<v.s.size()&&(v.s[i]=='e'||v.s[i]=='E')){++i;if(i<v.s.size()&&(v.s[i]=='+'||v.s[i]=='-'))++i;auto b=i;while(i<v.s.size()&&std::isdigit(static_cast<unsigned char>(v.s[i])))++i;need(i>b,"empty exponent");}need(i==v.s.size(),"invalid number tail");}}
  --depth;return v;
 }
 J run(){auto v=value();ws();need(p==s.size(),"JSON trailing data");return v;}
};
J json(const std::string&b){need(b.size()<1000000,"bounded JSON size");return Parser{b}.run();}
std::vector<int>ints(const J&j){need(j.kind==J::array,"integer array expected");std::vector<int>r;for(const auto&v:j.a)r.push_back(v.integer());return r;}
void keys(const J&j,std::initializer_list<const char*>list){std::set<std::string>e;for(auto k:list)e.insert(k);std::set<std::string>a;for(const auto&[k,v]:j.o)a.insert(k);need(j.kind==J::object&&a==e,"object keys mismatch");}
using Set=std::vector<int>;
struct Universe {
 std::array<std::bitset<501>,501>adj{};std::array<std::vector<Set>,7>sets;std::vector<Set>packings;std::string graph_hash,stable_hash,packing_hash;
 explicit Universe(const std::string&raw){
  graph_hash=hash(raw);need(graph_hash==graph_sha256,"graph byte identity");std::istringstream in(raw);std::string line;int edges=0;bool header=false;
  while(std::getline(in,line)){std::istringstream f(line);std::string tag;if(!(f>>tag)||tag=="c")continue;if(tag=="p"){std::string kind,extra;int n,m;need(!header&&bool(f>>kind>>n>>m)&&!(f>>extra)&&(kind=="edge"||kind=="col"||kind=="edges")&&n==500&&m==224874,"DIMACS header");header=true;}else{int u,v;std::string extra;need(tag=="e"&&header&&bool(f>>u>>v)&&!(f>>extra)&&u>=1&&u<=500&&v>=1&&v<=500&&u!=v&&!adj[u][v],"DIMACS edge");adj[u].set(v);adj[v].set(u);++edges;}}
  need(header&&edges==112437,"edge count");Set prefix,candidates(500);std::iota(candidates.begin(),candidates.end(),1);
  std::function<void(const Set&)>walk=[&](const Set&cand){if(!prefix.empty())sets[prefix.size()].push_back(prefix);if(prefix.size()==6)return;for(std::size_t i=0;i<cand.size();++i){int v=cand[i];Set next;for(std::size_t j=i+1;j<cand.size();++j)if(!adj[v][cand[j]])next.push_back(cand[j]);prefix.push_back(v);walk(next);prefix.pop_back();}};walk(candidates);
  const std::array<std::size_t,7> expected={0,500,12313,19901,2428,23,0};for(int k=1;k<=6;++k)need(sets[k].size()==expected[k],"stable census size "+std::to_string(k));std::ostringstream st;for(int k=1;k<=5;++k)for(const auto&S:sets[k]){st<<k<<':';for(std::size_t i=0;i<S.size();++i){if(i)st<<',';st<<S[i];}st<<'\n';}stable_hash=hash(st.str());
  std::vector<std::bitset<501>>masks;for(const auto&S:sets[5]){std::bitset<501>b;for(int v:S)b.set(v);masks.push_back(b);}Set chosen;int best=0;std::function<void(int,std::bitset<501>)>pack=[&](int i,std::bitset<501>used){if(int(chosen.size())+23-i<best)return;if(i==23){if(int(chosen.size())>best){best=chosen.size();packings.clear();}if(int(chosen.size())==best)packings.push_back(chosen);return;}if((used&masks[i]).none()){chosen.push_back(i+1);pack(i+1,used|masks[i]);chosen.pop_back();}pack(i+1,used);};pack(0,{});std::sort(packings.begin(),packings.end());need(best==15&&packings.size()==8,"maximum packing census");
  std::ostringstream ps;for(std::size_t i=0;i<packings.size();++i){ps<<'P'<<i+1<<':';for(std::size_t j=0;j<packings[i].size();++j){if(j)ps<<',';ps<<packings[i][j];}ps<<'\n';}packing_hash=hash(ps.str());
 }
};
void reconstruction(const J&d,const Universe&u){
 need(d.at("schema").text()=="dsjc5009_reconstruction_v1","reconstruction schema");
 need(d.at("graph_sha256").text()==u.graph_hash&&d.at("stable_sets_sha256").text()==u.stable_hash&&d.at("top_packings_sha256").text()==u.packing_hash,"reconstruction universe hashes");
 need(d.at("vertices").integer()==500&&d.at("undirected_edges").integer()==112437,"reconstruction graph counts");
 need(d.at("maximum_stable_set_size").integer()==5&&d.at("maximum_stable_set_packing_size").integer()==15&&d.at("maximum_top_packing_count").integer()==int(u.packings.size()),"reconstruction maximum counts");
 for(int k=1;k<=5;++k)need(d.at("stable_set_counts").at(std::to_string(k)).integer()==int(u.sets[k].size()),"reconstruction stable-set counts");
 const auto&packings=d.at("top_packings_one_based_indices");
 need(packings.kind==J::array&&packings.a.size()==u.packings.size(),"reconstruction packing array");
 for(std::size_t i=0;i<u.packings.size();++i)need(ints(packings.a[i])==u.packings[i],"reconstruction packing order");
 std::cout<<"RECONSTRUCTION counts_and_order PASS\n";
}
struct Row{int packing;std::array<int,5>h;};
long long objective(const std::array<int,5>&h){long long g=0,z=0;for(int i=4;i>=0;--i){g+=h[i];z+=g*(g+1)/2;}return z;}
Row verify(const J&d,const Universe&u,bool verbose){
 keys(d,{"schema","graph_sha256","stable_sets_sha256","top_packings_sha256","packing","label","target_h2_h3_h4","top_packing_one_based_indices","denominator","support_size","terms","exact_checks","active_vertex_rows","lp_discovery","peak_rss_kib"});
 need(d.at("schema").text()=="dsjc5009_fractional_profile_witness_v1","witness schema");need(d.at("graph_sha256").text()==u.graph_hash&&d.at("stable_sets_sha256").text()==u.stable_hash&&d.at("top_packings_sha256").text()==u.packing_hash,"reconstructed universe hashes");
 int p=d.at("packing").integer();auto label=d.at("label").text();need((p==5&&(label=="E"||label=="F"))||(p==7&&label=="F"),"current endpoint identity");Set target=label=="E"?Set{4,4,101}:Set{1,5,101};need(ints(d.at("target_h2_h3_h4"))==target,"target totals");auto top=ints(d.at("top_packing_one_based_indices"));need(top==u.packings[p-1],"exact top packing binding");std::bitset<501>removed;for(int i:top)for(int v:u.sets[5][i-1]){need(!removed[v],"top overlap");removed.set(v);}need(removed.count()==75,"fixed vertex total");
 Big D=d.at("denominator").big();need(D.cmp(Big())>0,"positive denominator");std::array<Big,501>loads;std::array<Big,5>counts;std::set<Set>seen;const auto&terms=d.at("terms");need(terms.kind==J::array&&int(terms.a.size())==d.at("support_size").integer()&&!terms.a.empty(),"support size");
 for(const auto&t:terms.a){keys(t,{"set","size","numerator"});auto S=ints(t.at("set"));int k=t.at("size").integer();Big num=t.at("numerator").big();need(k>=2&&k<=4&&S.size()==std::size_t(k)&&std::is_sorted(S.begin(),S.end())&&std::adjacent_find(S.begin(),S.end())==S.end()&&seen.insert(S).second&&num.cmp(Big())>0,"supported column form");need(std::binary_search(u.sets[k].begin(),u.sets[k].end(),S),"complete-universe membership");for(int v:S){need(v>=1&&v<=500&&!removed[v],"residual membership");loads[v].add(num);}counts[k].add(num);}
 Big deficit,mx;int saturated=0;for(int v=1;v<=500;++v){if(removed[v]){need(loads[v].cmp(Big())==0,"fixed vertex load");continue;}need(loads[v].cmp(D)<=0,"vertex capacity");deficit.add(D.minus(loads[v]));if(loads[v].cmp(D)==0)++saturated;if(loads[v].cmp(mx)>0)mx=loads[v];}
 for(int k=2;k<=4;++k){need(counts[k].cmp(D.times(target[k-2]))==0,"exact size total");}
 std::array<int,5>h={425-2*target[0]-3*target[1]-4*target[2],target[0],target[1],target[2],15};need(h[0]>=0&&deficit.cmp(D.times(h[0]))==0&&objective(h)==29791,"singleton completion and objective");
 const auto&checks=d.at("exact_checks");keys(checks,{"max_vertex_numerator","count_numerators"});need(checks.at("max_vertex_numerator").big().cmp(mx)==0,"stored maximum load");const auto&cn=checks.at("count_numerators");need(cn.kind==J::array&&cn.a.size()==3,"stored count array");for(int k=2;k<=4;++k)need(cn.a[k-2].big().cmp(counts[k])==0,"stored exact count");
 if(verbose){std::cout<<"P"<<p<<label<<" support="<<terms.a.size()<<" denominator="<<D.str()<<" exact_saturated_rows="<<saturated<<" singleton_total="<<h[0]<<" objective="<<objective(h)<<" EXACT_FEASIBLE\n";}
 return {p,h};
}
std::vector<std::string>split(const std::string&s,char d){std::istringstream f(s);std::vector<std::string>r;std::string v;while(std::getline(f,v,d))r.push_back(v);return r;}
void profiles(){
 // All canonical colorings have at least ceil(500/5)=100 classes, while
 // T(244)>29847.  Solve mass and class-count equations for h1 and h2.
 int total=0,capped=0,at789=0,at790=0;
 for(int q=100;q<=243;++q)for(int h5=0;h5<=15;++h5)
 for(int h4=0;h4<=(500-5*h5)/4;++h4)
 for(int h3=0;h3<=(500-5*h5-4*h4)/3;++h3){
  int h2=500-q-2*h3-3*h4-4*h5,h1=2*q-500+h3+2*h4+3*h5;
  if(h1<0||h2<0)continue;
  const std::array<int,5>h={h1,h2,h3,h4,h5};auto o=objective(h);
  if(o>29847)continue;
  need(h5==15,"threshold profile below maximum top cardinality");++total;
  if(h4<=101)++capped;
  if(o==29789)++at789;
  if(o==29790)++at790;
  if(o==29789||o==29790){
   need(h1+2*h2+3*h3+4*h4+5*h5==500&&h4>101,"graph-free counterprofile restriction");
   std::cout<<"GRAPH_FREE_PROFILE objective="<<o<<" h="<<h1<<','<<h2<<','<<h3<<','<<h4<<','<<h5<<" exceeds_h4_101\n";
  }
 }
 need(total==230&&capped==160&&at789==2&&at790==2,"complete threshold arithmetic census");
 std::cout<<"PROFILE_ARITHMETIC full=230 all_h5=15 h4_le101=160"
          <<" graph_free_at29789="<<at789<<" graph_free_at29790="<<at790<<" PASS\n";
}
void rejection_control(const J&d,const Universe&u,const std::string&name,const std::string&expected){
 try{verify(d,u,false);}catch(const std::exception&e){
  need(e.what()==expected,"unexpected negative-control failure for "+name+": "+e.what());
  std::cout<<"NEGATIVE_CONTROL "<<name<<" REJECTED "<<e.what()<<'\n';return;
 }
 throw std::runtime_error("semantic mutation accepted: "+name);
}
int main(int argc,char**argv){try{
 need(argc==4,"usage: check_endpoint_points GRAPH POINT_DIRECTORY UNRESOLVED_CSV");
 Inputs input(argv[1],argv[2],argv[3]);
 std::cout<<"INPUT_IDENTITIES six_fixed_files PASS\n";
 need(Big("999999999").add(Big("1")).str()=="1000000000"&&Big("1000000000000000000").minus(Big("1")).str()=="999999999999999999"&&Big("999999999999999999999999999").times(500).str()=="499999999999999999999999999500","exact integer self checks");Universe u(input.graph);std::cout<<"UNIVERSE graph="<<u.graph_hash<<" stable="<<u.stable_hash<<" top_packings="<<u.packing_hash<<" counts=500/12313/19901/2428/23/0 maximum_top=15 scenarios=8 PASS\n";
 reconstruction(json(input.reconstruction),u);
 profiles();
 std::set<std::pair<int,std::array<int,5>>>endpoints;int cells=0,high=0;std::istringstream csv(input.census);std::string line;need(bool(std::getline(csv,line)),"CSV header");if(!line.empty()&&line.back()=='\r')line.pop_back();auto head=split(line,',');std::map<std::string,std::size_t>cols;for(std::size_t i=0;i<head.size();++i)cols[head[i]]=i;
 while(std::getline(csv,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();if(line.empty())continue;auto v=split(line,',');auto at=[&](const std::string&k){need(cols.count(k)&&cols[k]<v.size(),"CSV field "+k);return v[cols[k]];};int p=std::stoi(at("packing")),o=std::stoi(at("objective"));std::array<int,5>h;for(int k=1;k<=5;++k)h[k-1]=std::stoi(at("h"+std::to_string(k)));need(objective(h)==o&&o>=29791&&o<=29847&&at("status")=="unresolved","census row scope");++cells;if(o==29791)need(endpoints.insert({p,h}).second,"duplicate endpoint");else ++high;}
 need(cells==1165&&high==1162&&endpoints.size()==3,"census endpoint scope");
 for(std::size_t i=0;i<input.points.size();++i){
  const std::string name=point_files[i].first;auto d=json(input.points[i]);auto row=verify(d,u,true);
  need(endpoints.erase({row.packing,row.h})==1,"point-to-census mapping");
  std::cout<<"POINT_HASH "<<name<<" "<<hash(input.points[i])<<'\n';
  auto changed=d;auto&num=changed.at("terms").a.front().at("numerator");num.s=num.big().add(Big("1")).str();
  rejection_control(changed,u,name+" numerator_plus_one","vertex capacity");
  changed=d;changed.at("denominator").s="0";
  rejection_control(changed,u,name+" zero_denominator","positive denominator");
  changed=d;auto&top=changed.at("top_packing_one_based_indices").a;std::swap(top[0],top[1]);
  rejection_control(changed,u,name+" changed_top_order","exact top packing binding");
 }
 need(endpoints.empty(),"unmatched endpoint");std::cout<<"CENSUS_MAPPING cells=1165 endpoint_cells=3 higher_cells=1162 PASS\nDSJC500_CURRENT_ENDPOINT_POINTS_PASS\n";return 0;
 }catch(const std::exception&e){std::cerr<<"DSJC500_CURRENT_ENDPOINT_POINTS_FAIL: "<<e.what()<<'\n';return 1;}}
