#include "Highs.h"
#include <chrono>
#include <cmath>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <sched.h>

// This driver receives only the generated model. It has no graph-specific
// objective target, MIP start, profile frontier, or external certificate.
volatile std::sig_atomic_t stop_requested=0;
void stop_handler(int){stop_requested=1;}
void check(HighsStatus s,const std::string& what){if(s==HighsStatus::kError)throw std::runtime_error(what);}
struct Trace {
    std::ofstream events;
    std::chrono::steady_clock::time_point start;
    std::string prefix;
    const HighsLp* lp=nullptr;
};
void callback(int type,const char*,const HighsCallbackDataOut* out,HighsCallbackDataIn* in,void* data) {
    auto& t=*static_cast<Trace*>(data);
    if(type==kCallbackMipInterrupt){if(stop_requested)in->user_interrupt=1;return;}
    const double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-t.start).count();
    t.events<<std::setprecision(17)<<type<<'\t'<<wall<<'\t'<<out->running_time<<'\t'
            <<out->objective_function_value<<'\t'<<out->mip_primal_bound<<'\t'<<out->mip_dual_bound<<'\t'
            <<out->mip_gap<<'\t'<<out->mip_node_count<<'\t'<<out->mip_total_lp_iterations<<'\n';
    t.events.flush();
    if(type==kCallbackMipImprovingSolution && out->mip_solution && out->mip_solution_size==t.lp->num_col_) {
        std::ofstream raw(t.prefix+".incumbent_latest.tsv.tmp");raw<<std::setprecision(17);
        for(HighsInt j=0;j<t.lp->num_col_;++j)raw<<t.lp->col_names_[j]<<'\t'<<out->mip_solution[j]<<'\n';
        raw.close();std::rename((t.prefix+".incumbent_latest.tsv.tmp").c_str(),(t.prefix+".incumbent_latest.tsv").c_str());
    }
}
double seconds(const timeval& x){return x.tv_sec+x.tv_usec*1e-6;}
int main(int argc,char** argv) {
 try {
    if(argc!=4)throw std::runtime_error("usage: solve MODEL.mps (lp|mip) OUTPUT_PREFIX");
    const std::string mode=argv[2],prefix=argv[3];
    if(mode!="lp"&&mode!="mip")throw std::runtime_error("invalid mode");
    Highs highs;
    std::cout<<"DRIVER HiGHS="<<highs.version()<<" githash="<<highs.githash()<<" mode="<<mode<<"\n";
    cpu_set_t affinity;CPU_ZERO(&affinity);
    if(sched_getaffinity(0,sizeof(affinity),&affinity)!=0)throw std::runtime_error("affinity query failed");
    if(CPU_COUNT(&affinity)!=1)throw std::runtime_error("driver requires exactly one allowed CPU");
    for(int c=0;c<CPU_SETSIZE;++c)if(CPU_ISSET(c,&affinity))std::cout<<"DRIVER cpu="<<c<<"\n";
    check(highs.setOptionValue("threads",1),"threads");
    check(highs.setOptionValue("parallel",std::string("off")),"parallel off");
    check(highs.setOptionValue("mip_rel_gap",0.0),"relative gap");
    check(highs.setOptionValue("mip_abs_gap",0.0),"absolute gap");
    check(highs.setOptionValue("mip_report_level",2),"MIP reporting");
    check(highs.setOptionValue("log_dev_level",1),"developer log");
    check(highs.readModel(argv[1]),"read model");
    if(mode=="lp")check(highs.clearIntegrality(),"relax integrality");
    check(highs.writeOptions(prefix+".options",false),"write options");
    check(highs.writeOptions(prefix+".nondefault_options",true),"write option deviations");
    check(highs.writeModel(prefix+".loaded.mps"),"write loaded model");
    Trace trace;trace.prefix=prefix;trace.lp=&highs.getLp();
    trace.events.open(prefix+".events.tsv");
    trace.events<<"callback_type\twall_seconds\tsolver_seconds\tobjective\tprimal_bound\tdual_bound\tgap\tnodes\tlp_iterations\n";
    check(highs.setCallback(callback,&trace),"set callback");
    if(mode=="mip") {
        check(highs.startCallback(kCallbackMipImprovingSolution),"improving callback");
        check(highs.startCallback(kCallbackMipLogging),"logging callback");
        check(highs.startCallback(kCallbackMipInterrupt),"interrupt callback");
    }
    std::signal(SIGTERM,stop_handler);std::signal(SIGINT,stop_handler);
    rusage before{},after{};getrusage(RUSAGE_SELF,&before);
    trace.start=std::chrono::steady_clock::now();
    const auto run_status=highs.run();
    const double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-trace.start).count();
    getrusage(RUSAGE_SELF,&after);
    check(highs.writeInfo(prefix+".info"),"write info");
    const auto& info=highs.getInfo();
    std::ofstream result(prefix+".summary.txt");
    result<<std::setprecision(17)<<"solver=HiGHS\nversion="<<highs.version()<<"\nthreads=1\nmode="<<mode
          <<"\nstatus="<<highs.modelStatusToString(highs.getModelStatus())
          <<"\nrun_status="<<static_cast<int>(run_status)<<"\nstop_requested="<<stop_requested
          <<"\nsolve_wall_seconds="<<wall<<"\nsolve_cpu_seconds="<<seconds(after.ru_utime)+seconds(after.ru_stime)-seconds(before.ru_utime)-seconds(before.ru_stime)
          <<"\npeak_rss_kib="<<after.ru_maxrss<<"\nobjective="<<info.objective_function_value
          <<"\nmip_dual_bound="<<info.mip_dual_bound<<"\nmip_gap="<<info.mip_gap<<"\nmip_nodes="<<info.mip_node_count
          <<"\nsimplex_iterations="<<info.simplex_iteration_count<<"\nipm_iterations="<<info.ipm_iteration_count
          <<"\npdlp_iterations="<<info.pdlp_iteration_count<<"\n";
    const auto& solution=highs.getSolution();
    if(solution.value_valid) {
        check(highs.writeSolution(prefix+".solution",0),"write raw solution");
        std::ofstream cols(prefix+".columns.tsv");cols<<std::setprecision(17);
        const auto& lp=highs.getLp();
        for(HighsInt j=0;j<lp.num_col_;++j)cols<<lp.col_names_[j]<<'\t'<<solution.col_value[j]<<'\n';
    }
    std::cout<<"DRIVER status="<<highs.modelStatusToString(highs.getModelStatus())<<" objective="<<std::setprecision(17)<<info.objective_function_value<<" wall="<<wall<<"\n";
    check(run_status,"solver run failed");
    return highs.getModelStatus()==HighsModelStatus::kOptimal?0:2;
 }catch(const std::exception& e){std::cerr<<"ERROR: "<<e.what()<<'\n';return 1;}
}
