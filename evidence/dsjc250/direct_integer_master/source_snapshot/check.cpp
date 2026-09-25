#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

// Independent input, universe, model and returned-witness checker. It does
// not include the enumerator or solver headers and has no expected optimum.
void need(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
long long integer(const std::string& s){size_t used=0;const auto value=std::stoll(s,&used);need(used==s.size(),"noninteger MPS value");return value;}
std::string padded(char prefix,int v,int width){std::ostringstream s;s<<prefix<<std::setw(width)<<std::setfill('0')<<v;return s.str();}
using Matrix=std::map<std::pair<std::string,std::string>,long long>;
int main(int argc,char** argv) {
 try {
    need(argc==4||argc==6,"usage: check GRAPH SETS MPS [COLUMN_VALUES OUTPUT_PREFIX]");
    std::ifstream graph(argv[1]);need(bool(graph),"graph open");
    int n=0,m=-1;std::set<std::pair<int,int>> edges;std::string line;
    while(std::getline(graph,line)) {
        std::istringstream s(line);std::string kind,extra;if(!(s>>kind)||kind=="c")continue;
        if(kind=="p"){std::string type;need(n==0 && bool(s>>type>>n>>m),"bad graph header");need((type=="edge"||type=="col")&&n>0&&m>=0,"graph type/dimensions");}
        else {int u,v;need(kind=="e"&&n>0&&bool(s>>u>>v),"bad graph edge");need(u>0&&v>0&&u<=n&&v<=n&&u!=v,"edge range");if(u>v)std::swap(u,v);need(edges.emplace(u,v).second,"duplicate edge");}
        need(!(s>>extra),"graph trailing data");
    }
    need(graph.eof()&&!graph.bad()&&n>0&&edges.size()==static_cast<size_t>(m),"graph incomplete");
    auto adjacent=[&](int u,int v){if(u>v)std::swap(u,v);return edges.contains({u,v});};
    std::ifstream file(argv[2]);need(bool(file),"sets open");
    std::vector<std::vector<int>> sets;std::set<std::vector<int>> universe;int alpha=0;
    while(std::getline(file,line)) {
        std::istringstream s(line);int id,size,v;need(bool(s>>id>>size)&&size>0&&id==static_cast<int>(sets.size()+1),"stable-set index/size");
        std::vector<int> set;for(int j=0;j<size;++j){need(bool(s>>v)&&v>0&&v<=n,"stable-set vertex");set.push_back(v);}
        std::string extra;need(!(s>>extra),"stable-set trailing data");
        need(std::is_sorted(set.begin(),set.end())&&std::adjacent_find(set.begin(),set.end())==set.end(),"stable-set order");
        for(size_t i=0;i<set.size();++i)for(size_t j=i+1;j<set.size();++j)need(!adjacent(set[i],set[j]),"unstable listed set");
        need(universe.insert(set).second,"duplicate stable set");
        if(!sets.empty())need(sets.back().size()<set.size()||(sets.back().size()==set.size()&&sets.back()<set),"noncanonical stable-set list");
        alpha=std::max(alpha,size);sets.push_back(set);
    }
    need(file.eof()&&!file.bad()&&!sets.empty(),"sets incomplete");
    for(int v=1;v<=n;++v)need(universe.contains({v}),"missing singleton");
    size_t extensions=0;
    // Prefix closure proves completeness without trusting the DFS: every
    // stable set is obtained by extending its sorted prefix by its last vertex.
    for(const auto& set:sets)for(int v=set.back()+1;v<=n;++v) {
        bool ok=true;for(int u:set)if(adjacent(u,v)){ok=false;break;}
        if(ok){auto extended=set;extended.push_back(v);need(universe.contains(extended),"missing compatible stable-set extension");++extensions;}
    }
    std::map<int,int> census;for(const auto& s:sets)++census[static_cast<int>(s.size())];
    std::cout<<"PASS universe_complete n="<<n<<" m="<<m<<" nonempty_sets="<<sets.size()<<" alpha="<<alpha<<" prefix_extensions="<<extensions<<"\n";

    std::map<std::string,char> wanted_rows,rows;
    std::map<std::string,long long> wanted_rhs,rhs,wanted_obj,obj;
    std::map<std::string,std::pair<char,long long>> wanted_bounds,bounds;
    std::set<std::string> wanted_binary,marker_binary;
    Matrix wanted_matrix,matrix;
    wanted_rows["OBJ"]='N';
    for(int v=1;v<=n;++v){auto name=padded('v',v,4);wanted_rows[name]='E';wanted_rhs[name]=1;}
    for(int t=1;t<=alpha;++t)wanted_rows["l"+std::to_string(t)]='E';
    for(size_t i=0;i<sets.size();++i){auto name=padded('x',static_cast<int>(i+1),6);wanted_binary.insert(name);wanted_bounds[name]={'B',1};
        for(int v:sets[i])wanted_matrix[{name,padded('v',v,4)}]=1;
        for(size_t t=1;t<=sets[i].size();++t)wanted_matrix[{name,"l"+std::to_string(t)}]=-1;
    }
    for(int t=1;t<=alpha;++t)for(int j=1;j<=n/t;++j){std::ostringstream name;name<<'y'<<t<<'_'<<std::setw(3)<<std::setfill('0')<<j;
        wanted_bounds[name.str()]={'U',1};wanted_obj[name.str()]=j;wanted_matrix[{name.str(),"l"+std::to_string(t)}]=1;
    }
    std::ifstream model(argv[3]);need(bool(model),"MPS open");std::string section;bool integer_region=false,ended=false,sense=false;
    while(std::getline(model,line)) {
        std::istringstream in(line);std::vector<std::string> token;std::string word;while(in>>word)token.push_back(word);if(token.empty())continue;
        if(token[0]=="NAME"){need(section.empty()&&token.size()==2,"MPS name");section="NAME";continue;}
        if(token[0]=="OBJSENSE"||token[0]=="ROWS"||token[0]=="COLUMNS"||token[0]=="RHS"||token[0]=="BOUNDS"){need(token.size()==1,"MPS section");section=token[0];continue;}
        if(token[0]=="ENDATA"){need(token.size()==1,"MPS end");ended=true;break;}
        if(section=="OBJSENSE"){need(token.size()==1&&token[0]=="MIN"&&!sense,"MPS sense");sense=true;}
        else if(section=="ROWS"){need(token.size()==2&&token[0].size()==1&&rows.emplace(token[1],token[0][0]).second,"MPS row");}
        else if(section=="COLUMNS") {
            need(token.size()==3,"MPS column syntax");
            if(token[1]=="'MARKER'"){need(token[2]=="'INTORG'"||token[2]=="'INTEND'","MPS integer marker");integer_region=token[2]=="'INTORG'";continue;}
            size_t used=0;long long value=std::stoll(token[2],&used);need(used==token[2].size(),"MPS noninteger coefficient");
            if(integer_region)marker_binary.insert(token[0]);
            if(token[1]=="OBJ")need(obj.emplace(token[0],value).second,"duplicate objective coefficient");
            else need(matrix.emplace(std::make_pair(token[0],token[1]),value).second,"duplicate matrix coefficient");
        }else if(section=="RHS"){need(token.size()==3&&token[0]=="RHS1","MPS RHS syntax");need(rhs.emplace(token[1],integer(token[2])).second,"duplicate RHS");}
        else if(section=="BOUNDS") {need(token.size()>=3&&token[1]=="BND1","MPS bound syntax");
            if(token[0]=="BV"){need(token.size()==3,"binary bound");need(bounds.emplace(token[2],std::make_pair('B',1)).second,"duplicate bound");}
            else {need(token[0]=="UP"&&token.size()==4,"continuous upper bound");need(bounds.emplace(token[2],std::make_pair('U',integer(token[3]))).second,"duplicate bound");}
        }else need(false,"unexpected MPS content");
    }
    while(std::getline(model,line))need(line.find_first_not_of(" \t\r")==std::string::npos,"MPS trailing data");
    need(ended&&sense&&!integer_region,"MPS incomplete");
    need(rows==wanted_rows&&rhs==wanted_rhs&&bounds==wanted_bounds&&obj==wanted_obj&&matrix==wanted_matrix&&marker_binary==wanted_binary,"MPS differs from exact unrestricted graph-derived formulation");
    std::cout<<"PASS model_exact rows="<<rows.size()-1<<" variables="<<bounds.size()<<" binary="<<wanted_binary.size()<<" continuous="<<bounds.size()-wanted_binary.size()<<" matrix_nnz="<<matrix.size()<<"\n";
    if(argc==4)return 0;

    std::ifstream solution(argv[4]);need(bool(solution),"solution open");std::map<std::string,double> values;
    while(std::getline(solution,line)){std::istringstream in(line);std::string name,extra;double x;need(bool(in>>name>>x)&&std::isfinite(x)&&!(in>>extra),"solution syntax");need(values.emplace(name,x).second,"duplicate solution column");}
    need(values.size()==bounds.size(),"solution dimension");
    for(const auto& [name,bound]:bounds){(void)bound;need(values.contains(name)&&values.at(name)>=-1e-6&&values.at(name)<=1+1e-6,"solution missing or outside bounds");}
    std::vector<int> cover(n+1),chosen;std::vector<long long> q(alpha+1);std::map<int,int> histogram;
    for(size_t i=0;i<sets.size();++i){double x=values.at(padded('x',static_cast<int>(i+1),6));need(std::abs(x-std::round(x))<=1e-6,"noninteger selected-set variable");if(x>0.5){chosen.push_back(static_cast<int>(i));for(int v:sets[i])need(++cover[v]==1,"overlapping selected sets");for(size_t t=1;t<=sets[i].size();++t)++q[t];++histogram[static_cast<int>(sets[i].size())];}}
    for(int v=1;v<=n;++v)need(cover[v]==1,"uncovered vertex");
    double linear_objective=0;
    for(int t=1;t<=alpha;++t){double cells=0;for(int j=1;j<=n/t;++j){std::ostringstream name;name<<'y'<<t<<'_'<<std::setw(3)<<std::setfill('0')<<j;const double y=values.at(name.str());cells+=y;linear_objective+=j*y;}need(std::abs(cells-q[t])<1e-5,"Ferrers linking equation");}
    std::sort(chosen.begin(),chosen.end(),[&](int a,int b){return sets[a].size()!=sets[b].size()?sets[a].size()>sets[b].size():sets[a]<sets[b];});
    std::vector<int> colour(n+1);long long direct=0,ferrers=0;
    std::ofstream witness(std::string(argv[5])+".coloring"),selected(std::string(argv[5])+".selected.tsv");
    for(size_t rank=0;rank<chosen.size();++rank){int id=chosen[rank];selected<<id+1<<'\t'<<sets[id].size();for(int v:sets[id]){colour[v]=static_cast<int>(rank+1);selected<<'\t'<<v;}selected<<'\n';}
    for(auto [u,v]:edges)need(colour[u]!=colour[v],"monochromatic reconstructed edge");
    for(int v=1;v<=n;++v){direct+=colour[v];witness<<v<<' '<<colour[v]<<'\n';}
    for(int t=1;t<=alpha;++t)ferrers+=q[t]*(q[t]+1)/2;
    need(direct==ferrers&&std::abs(linear_objective-direct)<1e-4,"objective mismatch");
    need(bool(witness)&&bool(selected),"witness output error");
    std::cout<<"PASS coloring vertices="<<n<<" edges_checked="<<m<<" classes="<<chosen.size()<<" direct_sum="<<direct<<" ferrers_sum="<<ferrers<<" linear_objective="<<std::setprecision(17)<<linear_objective<<"\nprofile=";
    for(int t=1;t<=alpha;++t)std::cout<<(t>1?",":"")<<histogram[t];
    std::cout<<"\nq=";for(int t=1;t<=alpha;++t)std::cout<<(t>1?",":"")<<q[t];std::cout<<'\n';
 }catch(const std::exception& e){std::cerr<<"REJECTED: "<<e.what()<<'\n';return 1;}
}
