#include <algorithm>
#include <bit>
#include <charconv>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

void require(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
struct Graph {int n=0;std::vector<std::vector<bool>> edge;std::set<std::pair<int,int>> edges;};
Graph read_graph(const std::string& file) {
    std::ifstream f(file);require(bool(f),"cannot open graph");
    Graph g;long long declared=-1;std::string line,tag,extra;
    while(std::getline(f,line)) {
        std::istringstream in(line);if(!(in>>tag)||tag=="c")continue;
        if(tag=="p") {
            std::string kind;require(g.n==0 && bool(in>>kind>>g.n>>declared),"invalid problem line");
            require((kind=="edge"||kind=="col") && g.n>0 && declared>=0,"bad dimensions/type");
            g.edge.assign(g.n+1,std::vector<bool>(g.n+1));
        }else {
            int u=0,v=0;require(tag=="e" && g.n>0 && bool(in>>u>>v),"invalid edge line");
            require(u>0 && v>0 && u<=g.n && v<=g.n && u!=v,"invalid edge endpoints");
            if(u>v)std::swap(u,v);
            require(g.edges.emplace(u,v).second,"duplicate undirected edge");
            g.edge[u][v]=g.edge[v][u]=true;
        }
        require(!(in>>extra),"unexpected trailing graph token");
    }
    require(!f.bad() && g.n>0 && static_cast<long long>(g.edges.size())==declared,"incomplete graph");
    return g;
}
using Sets=std::vector<std::vector<int>>;
Sets enumerate(const Graph& g) {
    Sets sets;std::vector<int> selected;
    std::function<void(const std::vector<int>&)> dfs=[&](const std::vector<int>& cand) {
        for(size_t i=0;i<cand.size();++i) {
            const int v=cand[i];selected.push_back(v);sets.push_back(selected);
            std::vector<int> next;
            for(size_t j=i+1;j<cand.size();++j)if(!g.edge[v][cand[j]])next.push_back(cand[j]);
            dfs(next);selected.pop_back();
        }
    };
    std::vector<int> all(g.n);std::iota(all.begin(),all.end(),1);dfs(all);
    std::sort(sets.begin(),sets.end(),[](const auto& a,const auto& b){return a.size()!=b.size()?a.size()<b.size():a<b;});
    return sets;
}
void selftest() {
    size_t tests=0;
    for(int n=1;n<=5;++n) {
        std::vector<std::pair<int,int>> pairs;
        for(int u=1;u<=n;++u)for(int v=u+1;v<=n;++v)pairs.emplace_back(u,v);
        for(unsigned mask=0;mask<(1U<<pairs.size());++mask) {
            Graph g;g.n=n;g.edge.assign(n+1,std::vector<bool>(n+1));
            for(size_t i=0;i<pairs.size();++i)if(mask&(1U<<i)){auto [u,v]=pairs[i];g.edge[u][v]=g.edge[v][u]=true;}
            Sets brute;
            for(unsigned subset=1;subset<(1U<<n);++subset) {
                std::vector<int> s;bool stable=true;
                for(int u=1;u<=n;++u)if(subset&(1U<<(u-1)))s.push_back(u);
                for(int u:s)for(int v:s)if(g.edge[u][v])stable=false;
                if(stable)brute.push_back(s);
            }
            const auto actual=enumerate(g);
            require(std::set<std::vector<int>>(actual.begin(),actual.end())==std::set<std::vector<int>>(brute.begin(),brute.end()),"enumerator self-test mismatch");
            require(std::set<std::vector<int>>(actual.begin(),actual.end()).size()==actual.size(),"duplicate enumerated set");++tests;
        }
    }
    std::cout<<"PASS exhaustive_small_graph_enumeration_tests="<<tests<<"\n";
}
std::string xname(size_t id){std::ostringstream s;s<<'x'<<std::setw(6)<<std::setfill('0')<<id;return s.str();}
std::string vname(int v){std::ostringstream s;s<<'v'<<std::setw(4)<<std::setfill('0')<<v;return s.str();}
std::string lname(int t){return "l"+std::to_string(t);}
std::string yname(int t,int j){std::ostringstream s;s<<'y'<<t<<'_'<<std::setw(3)<<std::setfill('0')<<j;return s.str();}
int main(int argc,char** argv) {
 try {
    if(argc==2 && std::string(argv[1])=="--self-test"){selftest();return 0;}
    require(argc==3,"usage: prepare GRAPH OUTPUT_DIRECTORY");
    const Graph g=read_graph(argv[1]);
    require(g.n==250 && g.edges.size()==27897,"input identity differs from requested graph");
    const Sets sets=enumerate(g);require(!sets.empty(),"no nonempty sets");
    const int alpha=static_cast<int>(sets.back().size());
    const std::string out=argv[2];
    std::ofstream edges(out+"/canonical_edges.txt");
    for(auto [u,v]:g.edges)edges<<u<<' '<<v<<'\n';
    std::ofstream list(out+"/stable_sets.tsv");std::vector<size_t> census(std::max(6,alpha)+1);
    for(size_t i=0;i<sets.size();++i){list<<i+1<<'\t'<<sets[i].size();for(int v:sets[i])list<<'\t'<<v;list<<'\n';++census[sets[i].size()];}
    std::ofstream counts(out+"/census.tsv");counts<<"size\tcount\n";
    for(size_t t=1;t<census.size();++t)counts<<t<<'\t'<<census[t]<<'\n';
    std::ofstream mps(out+"/master.mps");
    mps<<"NAME          DSJC2509\nOBJSENSE\n MIN\nROWS\n N  OBJ\n";
    for(int v=1;v<=g.n;++v)mps<<" E  "<<vname(v)<<'\n';
    for(int t=1;t<=alpha;++t)mps<<" E  "<<lname(t)<<'\n';
    mps<<"COLUMNS\n    MARK0000  'MARKER'                 'INTORG'\n";
    size_t matrix_nnz=0;
    for(size_t i=0;i<sets.size();++i){const auto name=xname(i+1);
        for(int v:sets[i]){mps<<"    "<<name<<"  "<<vname(v)<<"  1\n";++matrix_nnz;}
        for(size_t t=1;t<=sets[i].size();++t){mps<<"    "<<name<<"  "<<lname(static_cast<int>(t))<<"  -1\n";++matrix_nnz;}
    }
    mps<<"    MARK0001  'MARKER'                 'INTEND'\n";
    size_t cells=0;
    for(int t=1;t<=alpha;++t)for(int j=1;j<=g.n/t;++j){mps<<"    "<<yname(t,j)<<"  OBJ  "<<j<<"\n    "<<yname(t,j)<<"  "<<lname(t)<<"  1\n";++cells;++matrix_nnz;}
    mps<<"RHS\n";
    for(int v=1;v<=g.n;++v)mps<<"    RHS1  "<<vname(v)<<"  1\n";
    mps<<"BOUNDS\n";
    for(size_t i=0;i<sets.size();++i)mps<<" BV BND1  "<<xname(i+1)<<'\n';
    for(int t=1;t<=alpha;++t)for(int j=1;j<=g.n/t;++j)mps<<" UP BND1  "<<yname(t,j)<<"  1\n";
    mps<<"ENDATA\n";
    std::ofstream meta(out+"/model_dimensions.txt");
    meta<<"n="<<g.n<<"\nm="<<g.edges.size()<<"\nalpha="<<alpha<<"\ncolumns="<<sets.size()<<"\nrows="<<g.n+alpha<<"\nvariables="<<sets.size()+cells<<"\nbinary_variables="<<sets.size()<<"\ncontinuous_variables="<<cells<<"\nmatrix_nonzeros="<<matrix_nnz<<"\n";
    require(bool(edges)&&bool(list)&&bool(counts)&&bool(mps)&&bool(meta),"output write failure");
    std::cout<<"Complete stable universe enumerated without a size cutoff. n="<<g.n<<" m="<<g.edges.size()<<" alpha="<<alpha<<" sets="<<sets.size()<<" cells="<<cells<<" rows="<<g.n+alpha<<" matrix_nnz="<<matrix_nnz<<"\n";
    for(size_t t=1;t<census.size();++t)std::cout<<"stable_size_"<<t<<"="<<census[t]<<'\n';
 }catch(const std::exception& e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}
}
